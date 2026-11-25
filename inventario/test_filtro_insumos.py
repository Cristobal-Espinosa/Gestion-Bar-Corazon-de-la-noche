"""Filtro de insumos por estado de stock en /stock/ (BCDLN-26, RF-07)."""
import re

from django.test import TestCase
from django.urls import reverse

from inventario.tests import crear_trabajador

from .models import CategoriaInsumo, Insumo


class FiltroInsumosPorEstado(TestCase):
    def setUp(self):
        self.client.force_login(crear_trabajador())
        cat = CategoriaInsumo.objects.create(nombre="Licores")
        Insumo.objects.create(categoria=cat, nombre="Ron", stock_actual=3, stock_minimo=10)       # bajo el mínimo
        Insumo.objects.create(categoria=cat, nombre="Pisco", stock_actual=10, stock_minimo=10)    # justo en el mínimo
        Insumo.objects.create(categoria=cat, nombre="Vodka", stock_actual=0, stock_minimo=10)     # sin stock
        Insumo.objects.create(categoria=cat, nombre="Gin", stock_actual=50, stock_minimo=10)      # sobre el mínimo

    def nombres_en_tabla(self, estado=None):
        url = reverse("stock") + (f"?estado={estado}" if estado is not None else "")
        html = self.client.get(url).content.decode()
        tabla = re.search(r"<tbody>(.*?)</tbody>", html, re.S).group(1)
        return re.findall(r"<tr><td>([^<]+)</td>", tabla), tabla

    def test_todos_muestra_todos_los_insumos(self):
        nombres, _ = self.nombres_en_tabla()
        self.assertEqual(sorted(nombres), ["Gin", "Pisco", "Ron", "Vodka"])

    def test_bajo_el_minimo_incluye_menores_e_iguales_al_minimo(self):
        nombres, _ = self.nombres_en_tabla("bajo_minimo")
        self.assertEqual(sorted(nombres), ["Pisco", "Ron", "Vodka"])

    def test_sin_stock_muestra_solo_los_que_estan_en_cero(self):
        nombres, _ = self.nombres_en_tabla("sin_stock")
        self.assertEqual(nombres, ["Vodka"])

    def test_sin_resultados_muestra_mensaje(self):
        Insumo.objects.filter(stock_actual=0).update(stock_actual=5)
        nombres, tabla = self.nombres_en_tabla("sin_stock")
        self.assertEqual(nombres, [])
        self.assertIn("No hay insumos en este estado.", tabla)

    def test_todos_restablece_y_el_formulario_conserva_todos_los_insumos(self):
        filtrado = self.client.get(reverse("stock") + "?estado=sin_stock").content.decode()
        # El desplegable de "Actualizar stock" no se filtra: sigue ofreciendo los 4 insumos.
        self.assertEqual(len(re.findall(r"<option value=\"\d+\">", filtrado)), 4)
        nombres, _ = self.nombres_en_tabla("")
        self.assertEqual(len(nombres), 4)
