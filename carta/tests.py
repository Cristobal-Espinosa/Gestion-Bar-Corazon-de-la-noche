"""Casos de prueba de las restricciones (uno de éxito y uno de rechazo por regla).

Cada regla se comprueba en DOS niveles:
  * validación de la aplicación (lo que ve quien usa el admin) -> full_clean()
  * restricción de la base de datos (protege aunque se salte el admin) -> create()
"""
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from inventario.models import CategoriaInsumo, Insumo
from usuarios.models import Usuario

from .models import CategoriaCoctel, Coctel, RecetaCoctel
from .services import disponibilidad


class Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cat = CategoriaCoctel.objects.create(nombre="Clásicos")
        cls.cat_ins = CategoriaInsumo.objects.create(nombre="Licores")
        cls.ron = Insumo.objects.create(categoria=cls.cat_ins, nombre="Ron", stock_actual=500, stock_minimo=100)
        cls.lima = Insumo.objects.create(categoria=cls.cat_ins, nombre="Limón", stock_actual=0, stock_minimo=50)
        cls.mojito = Coctel.objects.create(categoria=cls.cat, nombre="Mojito", precio=5500)

    def assertRechazaConValidacion(self, objeto):
        with self.assertRaises(ValidationError):
            objeto.full_clean()

    def assertRechazaEnBD(self, fabrica):
        with self.assertRaises(IntegrityError), transaction.atomic():
            fabrica()


class RestriccionesCoctel(Base):
    def test_precio_cero_es_caso_limite_valido(self):
        Coctel(categoria=self.cat, nombre="Agua", precio=0).full_clean()

    def test_precio_negativo_rechazado(self):
        c = Coctel(categoria=self.cat, nombre="Malo", precio=-1)
        self.assertRechazaConValidacion(c)
        self.assertRechazaEnBD(lambda: Coctel.objects.create(categoria=self.cat, nombre="Malo", precio=-1))

    def test_nombre_repetido_rechazado_sin_distinguir_mayusculas_en_validacion(self):
        c = Coctel(categoria=self.cat, nombre="Mojito", precio=100)
        self.assertRechazaConValidacion(c)
        self.assertRechazaEnBD(lambda: Coctel.objects.create(categoria=self.cat, nombre="Mojito", precio=100))


class RestriccionesInsumoYReceta(Base):
    def test_nombre_de_insumo_repetido_rechazado(self):
        i = Insumo(categoria=self.cat_ins, nombre="Ron", stock_actual=1, stock_minimo=1)
        self.assertRechazaConValidacion(i)
        self.assertRechazaEnBD(lambda: Insumo.objects.create(categoria=self.cat_ins, nombre="Ron"))

    def test_stock_negativo_rechazado(self):
        i = Insumo(categoria=self.cat_ins, nombre="Gin", stock_actual=-5, stock_minimo=0)
        self.assertRechazaConValidacion(i)
        self.assertRechazaEnBD(lambda: Insumo.objects.create(categoria=self.cat_ins, nombre="Gin", stock_actual=-5))

    def test_cantidad_de_receta_valida(self):
        RecetaCoctel(coctel=self.mojito, insumo=self.ron, cantidad=60).full_clean()

    def test_cantidad_de_receta_cero_rechazada(self):
        r = RecetaCoctel(coctel=self.mojito, insumo=self.ron, cantidad=0)
        self.assertRechazaConValidacion(r)
        self.assertRechazaEnBD(lambda: RecetaCoctel.objects.create(coctel=self.mojito, insumo=self.ron, cantidad=0))

    def test_insumo_repetido_en_la_misma_receta_rechazado(self):
        RecetaCoctel.objects.create(coctel=self.mojito, insumo=self.ron, cantidad=60)
        dup = RecetaCoctel(coctel=self.mojito, insumo=self.ron, cantidad=30)
        self.assertRechazaConValidacion(dup)
        self.assertRechazaEnBD(lambda: RecetaCoctel.objects.create(coctel=self.mojito, insumo=self.ron, cantidad=30))

    def test_mismo_insumo_en_otro_coctel_es_valido(self):
        otro = Coctel.objects.create(categoria=self.cat, nombre="Daiquiri", precio=5000)
        RecetaCoctel.objects.create(coctel=self.mojito, insumo=self.ron, cantidad=60)
        RecetaCoctel(coctel=otro, insumo=self.ron, cantidad=60).full_clean()


class UsuarioDosApellidos(TestCase):
    def test_requiere_ambos_apellidos(self):
        u = Usuario(username="dueña", first_name="Ana", last_name="Pérez", apellido_2="", email="a@b.cl")
        with self.assertRaises(ValidationError):
            u.full_clean(exclude=["password"])


class Disponibilidad(Base):
    def test_disponible_si_alcanza_todo_y_cambia_al_bajar_el_stock(self):
        RecetaCoctel.objects.create(coctel=self.mojito, insumo=self.ron, cantidad=60)
        self.assertEqual(disponibilidad(Coctel.objects.get(pk=self.mojito.pk)), (True, []))
        self.ron.stock_actual = Decimal("10")
        self.ron.save()
        self.assertEqual(disponibilidad(Coctel.objects.get(pk=self.mojito.pk)), (False, ["Ron"]))

    def test_sin_receta_no_esta_disponible(self):
        self.assertEqual(disponibilidad(Coctel.objects.get(pk=self.mojito.pk)), (False, []))

    def test_vista_catalogo_entrega_estructura_esperada(self):
        RecetaCoctel.objects.create(coctel=self.mojito, insumo=self.lima, cantidad=30)
        oculto = Coctel.objects.create(categoria=self.cat, nombre="Oculto", precio=1, visible=False)
        resp = self.client.get(reverse("catalogo"))
        self.assertEqual(resp.status_code, 200)
        items = resp.context["cocteles"]
        self.assertEqual([i["obj"] for i in items], [self.mojito])   # el no visible no aparece
        self.assertFalse(items[0]["disponible"])
        self.assertEqual(items[0]["faltan"], ["Limón"])

    def test_paginas_del_frontend_responden(self):
        for nombre in ("inicio", "catalogo", "venta", "stock"):
            self.assertEqual(self.client.get(reverse(nombre)).status_code, 200, nombre)
