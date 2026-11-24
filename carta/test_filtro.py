"""Filtro por categoría de la carta (/carta/?categoria=<id>) y opción "Todas"."""
from html.parser import HTMLParser

from django.test import TestCase
from django.urls import reverse

from inventario.models import CategoriaInsumo, Insumo

from .models import CategoriaCoctel, Coctel, RecetaCoctel


class ContadorDiv(HTMLParser):
    """Comprueba que los <div> de la página quedan bien cerrados."""
    def __init__(self):
        super().__init__(); self.nivel = 0; self.minimo = 0
    def handle_starttag(self, tag, attrs):
        if tag == "div": self.nivel += 1
    def handle_endtag(self, tag):
        if tag == "div":
            self.nivel -= 1; self.minimo = min(self.minimo, self.nivel)


class FiltroPorCategoria(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.clasicos = CategoriaCoctel.objects.create(nombre="Clásicos")
        cls.autor = CategoriaCoctel.objects.create(nombre="De autor")
        cls.sin_alcohol = CategoriaCoctel.objects.create(nombre="Sin alcohol")   # sin cócteles
        cls.solo_ocultos = CategoriaCoctel.objects.create(nombre="Ocultos")      # cócteles no visibles
        ron = Insumo.objects.create(categoria=CategoriaInsumo.objects.create(nombre="Licores"), nombre="Ron", stock_actual=100, stock_minimo=10)
        cls.mojito = Coctel.objects.create(categoria=cls.clasicos, nombre="Mojito", precio=5500)
        cls.daiquiri = Coctel.objects.create(categoria=cls.clasicos, nombre="Daiquiri", precio=5000)
        cls.especial = Coctel.objects.create(categoria=cls.autor, nombre="Corazón", precio=7000)
        Coctel.objects.create(categoria=cls.solo_ocultos, nombre="Secreto", precio=1, visible=False)
        for c in (cls.mojito, cls.daiquiri, cls.especial):
            RecetaCoctel.objects.create(coctel=c, insumo=ron, cantidad=60)

    def pedir(self, categoria=None):
        url = reverse("catalogo") + (f"?categoria={categoria}" if categoria is not None else "")
        return self.client.get(url)

    def nombres(self, resp):
        return sorted(i["obj"].nombre for i in resp.context["cocteles"])

    def test_sin_parametro_es_todas(self):
        r = self.pedir()
        self.assertEqual(self.nombres(r), ["Corazón", "Daiquiri", "Mojito"])      # el oculto no sale
        self.assertIsNone(r.context["categoria_sel"])
        self.assertContains(r, ">Todas</a>")

    def test_filtra_por_categoria(self):
        self.assertEqual(self.nombres(self.pedir(self.clasicos.pk)), ["Daiquiri", "Mojito"])
        self.assertEqual(self.nombres(self.pedir(self.autor.pk)), ["Corazón"])

    def test_el_filtro_conserva_disponibilidad(self):
        r = self.pedir(self.autor.pk)
        self.assertTrue(r.context["cocteles"][0]["disponible"])

    def test_categoria_sin_cocteles_muestra_mensaje(self):
        for cat in (self.sin_alcohol, self.solo_ocultos):
            r = self.pedir(cat.pk)
            self.assertEqual(r.context["cocteles"], [])
            self.assertContains(r, f"No hay cócteles visibles en la categoría «{cat.nombre}».")
            self.assertNotContains(r, "Disponibles</a>")      # no se muestran las pestañas vacías

    def test_el_filtro_ofrece_todas_las_categorias_aunque_esten_vacias(self):
        r = self.pedir()
        for cat in (self.clasicos, self.autor, self.sin_alcohol, self.solo_ocultos):
            self.assertContains(r, f"?categoria={cat.pk}")
        self.assertEqual(len(r.context["categorias"]), 4)

    def test_categoria_activa_se_marca(self):
        html = self.pedir(self.autor.pk).content.decode()
        self.assertRegex(html, rf'active" href="/carta/\?categoria={self.autor.pk}"')
        self.assertNotRegex(html, r'active" href="/carta/">Todas')

    def test_valores_invalidos_equivalen_a_todas(self):
        for valor in ("abc", "99999", "0", "-1", "", "²", "1.5", "9" * 40, "1 OR 1=1", "%00"):
            r = self.pedir(valor)
            self.assertEqual(r.status_code, 200, valor)
            self.assertEqual(self.nombres(r), ["Corazón", "Daiquiri", "Mojito"], valor)
            self.assertIsNone(r.context["categoria_sel"], valor)

    def test_sin_categorias_ni_cocteles(self):
        Coctel.objects.all().delete(); CategoriaCoctel.objects.all().delete()
        r = self.pedir()
        self.assertContains(r, "No hay cócteles cargados.")
        self.assertNotContains(r, ">Todas</a>")

    def test_la_pagina_sigue_bien_cerrada_en_todos_los_casos(self):
        for categoria in (None, self.clasicos.pk, self.sin_alcohol.pk):
            parser = ContadorDiv(); parser.feed(self.pedir(categoria).content.decode())
            self.assertEqual((parser.nivel, parser.minimo), (0, 0), categoria)

    def test_es_publico(self):
        self.assertEqual(self.pedir(self.autor.pk).status_code, 200)    # sin iniciar sesión
