from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from carta.models import CategoriaCoctel, Coctel, RecetaCoctel
from inventario.models import CategoriaInsumo, Insumo, MovimientoInventario
from inventario.tests import crear_trabajador

from .models import DetalleVenta, Venta


class RegistroDeVenta(TestCase):
    def setUp(self):
        self.user = crear_trabajador()
        self.client.force_login(self.user)
        ci = CategoriaInsumo.objects.create(nombre="Licores")
        self.ron = Insumo.objects.create(categoria=ci, nombre="Ron", stock_actual=500, stock_minimo=100)
        self.azucar = Insumo.objects.create(categoria=ci, nombre="Azúcar", unidad_medida="cdta", stock_actual=3, stock_minimo=1)
        self.mojito = Coctel.objects.create(categoria=CategoriaCoctel.objects.create(nombre="Clásicos"), nombre="Mojito", precio=5500)
        RecetaCoctel.objects.create(coctel=self.mojito, insumo=self.ron, cantidad=60)
        RecetaCoctel.objects.create(coctel=self.mojito, insumo=self.azucar, cantidad=2)

    def vender(self, cantidad, coctel=None):
        r = self.client.post(reverse("venta"), {"coctel": (coctel or self.mojito).pk, "cantidad": cantidad}, follow=True)
        self.ron.refresh_from_db(); self.azucar.refresh_from_db()
        return r

    def test_venta_exitosa_descuenta_stock_y_deja_registros(self):
        r = self.vender(1)
        self.assertEqual((self.ron.stock_actual, self.azucar.stock_actual), (Decimal("440"), Decimal("1")))
        v = Venta.objects.get(); d = DetalleVenta.objects.get()
        self.assertEqual((v.usuario, d.coctel, d.cantidad, d.precio_unitario), (self.user, self.mojito, 1, 5500))
        movs = MovimientoInventario.objects.order_by("insumo__nombre")
        self.assertEqual([(m.insumo.nombre, m.cantidad, m.tipo_movimiento.nombre, m.usuario) for m in movs],
                         [("Azúcar", Decimal("-2"), "Venta", self.user), ("Ron", Decimal("-60"), "Venta", self.user)])
        self.assertContains(r, "Venta #%d registrada" % v.pk)
        self.assertContains(r, "$5.500")

    def test_venta_bloqueada_si_falta_un_insumo_y_no_cambia_nada(self):
        r = self.vender(2)          # azúcar: necesita 4, hay 3
        self.assertEqual((self.ron.stock_actual, self.azucar.stock_actual), (Decimal("500"), Decimal("3")))
        self.assertEqual((Venta.objects.count(), DetalleVenta.objects.count(), MovimientoInventario.objects.count()), (0, 0, 0))
        self.assertContains(r, "Venta bloqueada")
        self.assertContains(r, "Azúcar (necesita 4 cdta, hay 3)")
        self.assertNotContains(r, "Ron (necesita")        # solo lo que falta

    def test_caso_limite_justo_el_stock_necesario(self):
        self.azucar.stock_actual = 2; self.azucar.save()
        self.vender(1)
        self.assertEqual(self.azucar.stock_actual, 0)
        self.assertEqual(Venta.objects.count(), 1)

    def test_cantidad_invalida_se_marca_en_el_campo(self):
        for valor in ("0", "-3", "abc", "", "1001", "2.5"):
            r = self.vender(valor)
            self.assertEqual(Venta.objects.count(), 0, valor)
            self.assertTrue(r.context["error_cantidad"], valor)
            self.assertEqual(self.ron.stock_actual, Decimal("500"))

    def test_coctel_inexistente_o_oculto_rechazado(self):
        oculto = Coctel.objects.create(categoria=self.mojito.categoria, nombre="Oculto", precio=1, visible=False)
        RecetaCoctel.objects.create(coctel=oculto, insumo=self.ron, cantidad=1)
        self.assertContains(self.vender(1, coctel=oculto), "no existe")
        r = self.client.post(reverse("venta"), {"coctel": 9999, "cantidad": 1})
        self.assertContains(r, "no existe")
        self.assertEqual(Venta.objects.count(), 0)

    def test_coctel_sin_receta_rechazado(self):
        vacio = Coctel.objects.create(categoria=self.mojito.categoria, nombre="Vacío", precio=1)
        self.assertContains(self.vender(1, coctel=vacio), "no tiene receta")
        self.assertEqual(Venta.objects.count(), 0)

    def test_refrescar_la_pagina_no_repite_la_venta(self):
        self.vender(1)
        self.client.get(reverse("venta")); self.client.get(reverse("venta"))
        self.assertEqual(Venta.objects.count(), 1)

    def test_la_carta_refleja_el_stock_despues_de_vender(self):
        self.vender(1)    # azúcar queda en 1: ya no alcanza para otro mojito
        items = self.client.get(reverse("catalogo")).context["cocteles"]
        self.assertFalse(items[0]["disponible"])
        self.assertEqual(items[0]["faltan"], ["Azúcar"])
