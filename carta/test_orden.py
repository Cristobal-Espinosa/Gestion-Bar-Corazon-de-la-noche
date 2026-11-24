"""Orden de la carta: disponibles primero, no disponibles después (pestaña "Todos")."""
import re
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from inventario.models import CategoriaInsumo, Insumo

from .models import CategoriaCoctel, Coctel, RecetaCoctel

DISP, NO_DISP = "Disponible", "No disponible"


class OrdenDeLaCarta(TestCase):
    def setUp(self):
        self.ron = Insumo.objects.create(categoria=CategoriaInsumo.objects.create(nombre="Licores"),
                                         nombre="Ron", stock_actual=100, stock_minimo=10)
        self.sin_stock = Insumo.objects.create(categoria=self.ron.categoria, nombre="Gin", stock_actual=0, stock_minimo=10)
        self.a = CategoriaCoctel.objects.create(nombre="A Clásicos")
        self.b = CategoriaCoctel.objects.create(nombre="B De autor")
        # (nombre, categoría, insumo que usa): Ron alcanza, Gin no
        self.crear("B Alfa", self.b, self.ron)
        self.crear("A Zeta", self.a, self.sin_stock)
        self.crear("A Beta", self.a, self.ron)
        self.crear("B Beta", self.b, self.sin_stock)
        self.crear("A Alfa", self.a, self.sin_stock)

    def crear(self, nombre, categoria, insumo, visible=True):
        c = Coctel.objects.create(categoria=categoria, nombre=nombre, precio=1000, visible=visible)
        RecetaCoctel.objects.create(coctel=c, insumo=insumo, cantidad=60)
        return c

    def pestana_todos(self, url=None):
        """[(nombre, estado)] en el orden en que aparecen en la pestaña 'Todos' del HTML."""
        html = self.client.get(url or reverse("catalogo")).content.decode()
        todos = html.split('id="tab-1"')[1].split('id="tab-2"')[0]
        return re.findall(r'alt="([^"]+)".*?(No disponible|Disponible)</div>', todos, re.S)

    # --- criterios 1 y 2
    def test_disponibles_primero_y_dentro_de_cada_grupo_por_categoria_y_nombre(self):
        self.assertEqual(self.pestana_todos(), [
            ("A Beta", DISP), ("B Alfa", DISP),                                    # disponibles
            ("A Alfa", NO_DISP), ("A Zeta", NO_DISP), ("B Beta", NO_DISP),         # no disponibles
        ])

    # --- criterio 3
    def test_todos_siguen_accesibles_con_su_estado_visible(self):
        r = self.client.get(reverse("catalogo"))
        self.assertEqual(len(r.context["cocteles"]), 5)
        self.assertEqual(len(self.pestana_todos()), 5)
        # y siguen apareciendo en sus pestañas de siempre
        html = r.content.decode()
        disponibles = html.split('id="tab-2"')[1].split('id="tab-3"')[0]
        no_disponibles = html.split('id="tab-3"')[1]
        self.assertEqual(len(re.findall(r'alt="', disponibles)), 2)
        self.assertEqual(len(re.findall(r'alt="', no_disponibles)), 3)

    def test_los_ocultos_siguen_sin_aparecer(self):
        self.crear("Secreto", self.a, self.ron, visible=False)
        self.assertNotIn("Secreto", [n for n, _ in self.pestana_todos()])

    # --- criterio 4
    def test_si_baja_el_stock_el_coctel_pasa_a_no_disponibles(self):
        self.ron.stock_actual = Decimal("50")          # ya no alcanza para 60 ml
        self.ron.save()
        self.assertEqual(self.pestana_todos(), [
            ("A Alfa", NO_DISP), ("A Beta", NO_DISP), ("A Zeta", NO_DISP),
            ("B Alfa", NO_DISP), ("B Beta", NO_DISP),
        ])

    def test_si_sube_el_stock_el_coctel_pasa_a_disponibles(self):
        self.sin_stock.stock_actual = Decimal("200")
        self.sin_stock.save()
        self.assertEqual([e for _, e in self.pestana_todos()], [DISP] * 5)

    def test_un_coctel_pasa_de_grupo_y_mantiene_su_lugar_por_categoria_y_nombre(self):
        self.sin_stock.stock_actual = Decimal("100"); self.sin_stock.save()
        self.ron.stock_actual = Decimal("0"); self.ron.save()                  # se invierten los grupos
        self.assertEqual(self.pestana_todos(), [
            ("A Alfa", DISP), ("A Zeta", DISP), ("B Beta", DISP),
            ("A Beta", NO_DISP), ("B Alfa", NO_DISP),
        ])

    # --- convive con el filtro por categoría
    def test_el_orden_tambien_se_aplica_dentro_de_una_categoria(self):
        self.crear("A Aaa", self.a, self.sin_stock)
        r = self.pestana_todos(reverse("catalogo") + f"?categoria={self.a.pk}")
        self.assertEqual(r, [("A Beta", DISP), ("A Aaa", NO_DISP), ("A Alfa", NO_DISP), ("A Zeta", NO_DISP)])
