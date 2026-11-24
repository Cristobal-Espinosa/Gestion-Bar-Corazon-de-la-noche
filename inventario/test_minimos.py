"""Columnas "Mínimo" y "Reposición" de la pantalla de stock."""
import re
from decimal import Decimal
from html.parser import HTMLParser

from django.test import TestCase
from django.urls import reverse

from carta.models import CategoriaCoctel, Coctel, RecetaCoctel
from inventario.tests import crear_trabajador

from .models import CategoriaInsumo, Insumo
from .services import estado_reposicion


class ColumnasMinimoYReposicion(TestCase):
    def setUp(self):
        self.client.force_login(crear_trabajador())
        self.cat = CategoriaInsumo.objects.create(nombre="Licores")

    def insumo(self, nombre, actual, minimo, unidad="ml"):
        return Insumo.objects.create(categoria=self.cat, nombre=nombre, stock_actual=actual, stock_minimo=minimo, unidad_medida=unidad)

    def fila(self, nombre):
        html = self.client.get(reverse("stock")).content.decode()
        return re.search(rf"<tr><td>{nombre}</td>.*?</tr>", html, re.S).group(0)

    # --- criterio 1
    def test_cada_insumo_muestra_stock_y_minimo_con_sus_columnas(self):
        self.insumo("Ron", 30, 10)
        html = self.client.get(reverse("stock")).content.decode()
        for titulo in ("<th>Insumo</th>", "Stock</th>", "Mínimo</th>", "Reposición</th>"):
            self.assertIn(titulo, html)
        fila = self.fila("Ron")
        self.assertIn("30 ml", fila)      # stock actual
        self.assertIn("10 ml", fila)      # mínimo

    # --- criterio 2
    def test_bajo_el_minimo_indica_cuantas_unidades_faltan(self):
        self.insumo("Ron", 3, 10)
        fila = self.fila("Ron")
        self.assertIn("Faltan 7 ml", fila)
        self.assertNotIn("En el mínimo", fila)

    def test_faltante_con_decimales_y_otra_unidad(self):
        self.insumo("Azúcar", Decimal("2.5"), 10, unidad="cdta")
        self.assertRegex(self.fila("Azúcar"), r"Faltan 7[.,]50 cdta")

    def test_stock_en_cero_con_minimo_falta_todo_el_minimo(self):
        self.insumo("Ron", 0, 10)
        self.assertIn("Faltan 10 ml", self.fila("Ron"))

    # --- criterio 3
    def test_en_el_minimo_se_marca_sin_faltante(self):
        self.insumo("Ron", 10, 10)
        fila = self.fila("Ron")
        self.assertIn("En el mínimo", fila)
        self.assertNotIn("Faltan", fila)

    # --- criterio 4
    def test_sobre_el_minimo_no_hay_alerta(self):
        self.insumo("Ron", 11, 10)
        fila = self.fila("Ron")
        self.assertNotIn("Faltan", fila)
        self.assertNotIn("En el mínimo", fila)
        self.assertNotIn("badge", fila)

    def test_cada_insumo_se_evalua_por_separado(self):
        self.insumo("Ron", 3, 10); self.insumo("Gin", 10, 10); self.insumo("Vodka", 50, 10)
        self.assertIn("Faltan 7", self.fila("Ron"))
        self.assertIn("En el mínimo", self.fila("Gin"))
        self.assertNotIn("badge", self.fila("Vodka"))

    def test_regla_pura(self):
        ron = Insumo(stock_actual=Decimal("3"), stock_minimo=Decimal("10"))
        self.assertEqual(estado_reposicion(ron), ("bajo", Decimal("7")))
        ron.stock_actual = Decimal("10");  self.assertEqual(estado_reposicion(ron), ("minimo", Decimal("0")))
        ron.stock_actual = Decimal("10.01"); self.assertEqual(estado_reposicion(ron), ("ok", Decimal("0")))

    # --- criterio 5
    def test_se_actualiza_cuando_cambia_el_inventario(self):
        ron = self.insumo("Ron", 3, 10)
        self.assertIn("Faltan 7", self.fila("Ron"))
        # reposición desde la pantalla de stock (suma 7 -> queda justo en el mínimo)
        self.client.post(reverse("stock"), {"licor": ron.pk, "tipo": "reposicion", "cantidad": "7", "costo_unitario": "10"})
        self.assertIn("En el mínimo", self.fila("Ron"))
        # ajuste por conteo (fija 50 -> sobre el mínimo)
        self.client.post(reverse("stock"), {"licor": ron.pk, "tipo": "ajuste", "cantidad": "50"})
        self.assertNotIn("badge", self.fila("Ron"))
        # cambio directo en la base (por ejemplo desde el admin)
        ron.stock_actual = 4; ron.save()
        self.assertIn("Faltan 6", self.fila("Ron"))

    def test_una_venta_que_baja_el_stock_activa_el_aviso(self):
        ron = self.insumo("Ron", 70, 20)
        mojito = Coctel.objects.create(categoria=CategoriaCoctel.objects.create(nombre="Clásicos"), nombre="Mojito", precio=5500)
        RecetaCoctel.objects.create(coctel=mojito, insumo=ron, cantidad=60)
        self.assertNotIn("badge", self.fila("Ron"))
        self.client.post(reverse("venta"), {"coctel": mojito.pk, "cantidad": 1})      # 70 -> 10
        self.assertIn("Faltan 10 ml", self.fila("Ron"))


class PaginaBienFormada(TestCase):
    def test_los_div_de_la_pagina_de_stock_quedan_bien_cerrados(self):
        self.client.force_login(crear_trabajador())
        cat = CategoriaInsumo.objects.create(nombre="Licores")
        Insumo.objects.create(categoria=cat, nombre="Ron", stock_actual=3, stock_minimo=10)

        class Contador(HTMLParser):
            nivel = minimo = 0
            def handle_starttag(self, tag, attrs):
                if tag == "div": self.nivel += 1
            def handle_endtag(self, tag):
                if tag == "div":
                    self.nivel -= 1; self.minimo = min(self.minimo, self.nivel)

        c = Contador(); c.feed(self.client.get(reverse("stock")).content.decode())
        self.assertEqual((c.nivel, c.minimo), (0, 0))
