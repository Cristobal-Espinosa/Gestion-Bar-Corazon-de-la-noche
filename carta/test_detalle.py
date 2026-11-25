"""Detalle de cada cóctel en la carta (RF-03): nombre, descripción e ingredientes, sin precio."""
from django.test import TestCase
from django.urls import reverse

from inventario.models import CategoriaInsumo, Insumo

from .models import CategoriaCoctel, Coctel, RecetaCoctel


class DetalleDeCoctel(TestCase):
    @classmethod
    def setUpTestData(cls):
        cat = CategoriaCoctel.objects.create(nombre="Clásicos")
        ron = Insumo.objects.create(categoria=CategoriaInsumo.objects.create(nombre="Licores"), nombre="Ron",
                                    stock_actual=500, stock_minimo=100)
        cls.mojito = Coctel.objects.create(categoria=cat, nombre="Mojito", precio=5500, descripcion="Ron, lima y menta")
        cls.aperol = Coctel.objects.create(categoria=cat, nombre="Aperol", precio=4800)   # sin descripción ni receta
        RecetaCoctel.objects.create(coctel=cls.mojito, insumo=ron, cantidad=60)

    def pedir(self):
        return self.client.get(reverse("catalogo"))

    def test_detalle_muestra_nombre_descripcion_e_ingredientes(self):
        r = self.pedir()
        self.assertContains(r, f'id="detalle-{self.mojito.pk}"')
        self.assertContains(r, f'id="detalle-titulo-{self.mojito.pk}">Mojito<')
        self.assertContains(r, "Ron, lima y menta")
        self.assertContains(r, "Ron: 60")

    def test_detalle_no_muestra_precio(self):
        r = self.pedir()
        self.assertNotContains(r, "5500")
        self.assertNotContains(r, "4800")

    def test_ventana_se_puede_cerrar_y_volver_a_la_carta(self):
        self.assertContains(self.pedir(), 'data-bs-dismiss="modal"')

    def test_coctel_sin_descripcion_ni_receta_no_falla(self):
        r = self.pedir()
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, f'id="detalle-{self.aperol.pk}"')
        self.assertContains(r, "Sin ingredientes registrados.")

    def test_cada_detalle_corresponde_a_su_coctel(self):
        r = self.pedir()
        self.assertContains(r, f'data-bs-target="#detalle-{self.mojito.pk}"')
        self.assertContains(r, f'data-bs-target="#detalle-{self.aperol.pk}"')
