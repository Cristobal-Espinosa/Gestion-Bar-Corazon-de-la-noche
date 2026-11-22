from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from carta.models import CategoriaCoctel, Coctel, RecetaCoctel
from usuarios.models import Usuario

from .models import CategoriaInsumo, Compra, DetalleCompra, Insumo, MovimientoInventario


def crear_trabajador(username="barman"):
    return Usuario.objects.create_user(username, "b@bar.cl", "clave-segura-123",
                                       first_name="Ana", last_name="Pérez", apellido_2="Soto")


class AccesoPorLogin(TestCase):
    def test_visitante_ve_la_carta_pero_no_el_resto(self):
        self.assertEqual(self.client.get(reverse("catalogo")).status_code, 200)
        for nombre in ("venta", "stock"):
            r = self.client.get(reverse(nombre))
            self.assertRedirects(r, f"{reverse('login')}?next={reverse(nombre)}", fetch_redirect_response=False)
        # el POST tampoco entra sin sesión
        self.assertEqual(self.client.post(reverse("venta"), {"coctel": 1, "cantidad": 1}).status_code, 302)
        self.assertEqual(self.client.post(reverse("stock"), {}).status_code, 302)

    def test_portada_sin_sesion_lleva_a_la_carta(self):
        self.assertRedirects(self.client.get(reverse("inicio")), reverse("catalogo"), fetch_redirect_response=False)

    def test_menu_publico_no_muestra_login_ni_opciones_de_trabajadores(self):
        html = self.client.get(reverse("catalogo")).content.decode()
        self.assertNotIn(reverse("login"), html)
        self.assertNotIn(reverse("venta"), html)
        self.assertNotIn(reverse("stock"), html)

    def test_login_correcto_incorrecto_y_logout(self):
        crear_trabajador()
        r = self.client.post(reverse("login"), {"username": "barman", "password": "mala"})
        self.assertContains(r, "Usuario o contraseña incorrectos")
        r = self.client.post(reverse("login"), {"username": "barman", "password": "clave-segura-123"})
        self.assertRedirects(r, reverse("inicio"), fetch_redirect_response=False)
        html = self.client.get(reverse("catalogo")).content.decode()
        self.assertIn(reverse("venta"), html)          # ahora el menú muestra todo
        self.assertIn(reverse("logout"), html)
        self.assertEqual(self.client.get(reverse("stock")).status_code, 200)
        # cerrar sesión es por POST
        self.assertEqual(self.client.get(reverse("logout")).status_code, 405)
        r = self.client.post(reverse("logout"))
        self.assertRedirects(r, reverse("catalogo"), fetch_redirect_response=False)
        self.assertEqual(self.client.get(reverse("stock")).status_code, 302)

    def test_usuario_desactivado_no_entra(self):
        u = crear_trabajador(); u.is_active = False; u.save()
        r = self.client.post(reverse("login"), {"username": "barman", "password": "clave-segura-123"})
        self.assertContains(r, "Usuario o contraseña incorrectos")

    def test_login_vuelve_a_la_pagina_pedida(self):
        crear_trabajador()
        r = self.client.post(reverse("login") + "?next=/stock/", {"username": "barman", "password": "clave-segura-123", "next": "/stock/"})
        self.assertRedirects(r, "/stock/", fetch_redirect_response=False)


class AjusteManualDeStock(TestCase):
    def setUp(self):
        self.user = crear_trabajador()
        self.client.force_login(self.user)
        cat = CategoriaInsumo.objects.create(nombre="Licores")
        self.ron = Insumo.objects.create(categoria=cat, nombre="Ron", stock_actual=500, stock_minimo=100)

    def enviar(self, tipo, cantidad, insumo=None, costo="10"):
        datos = {"licor": (insumo or self.ron).pk, "tipo": tipo, "cantidad": cantidad}
        if costo is not None:
            datos["costo_unitario"] = costo
        r = self.client.post(reverse("stock"), datos, follow=True)
        self.ron.refresh_from_db()
        return r

    def test_reposicion_suma_y_registra_movimiento(self):
        r = self.enviar("reposicion", "250")
        self.assertEqual(self.ron.stock_actual, Decimal("750"))
        m = MovimientoInventario.objects.get()
        self.assertEqual((m.cantidad, m.usuario, m.tipo_movimiento.nombre), (Decimal("250"), self.user, "Reposición"))
        self.assertContains(r, "Stock de Ron actualizado")

    def test_ajuste_fija_el_stock_y_registra_la_diferencia(self):
        self.enviar("ajuste", "420")
        self.assertEqual(self.ron.stock_actual, Decimal("420"))
        m = MovimientoInventario.objects.get()
        self.assertEqual(m.cantidad, Decimal("-80"))
        self.assertIn("de 500 a 420", m.motivo)

    def test_ajuste_igual_al_stock_no_registra_nada(self):
        r = self.enviar("ajuste", "500")
        self.assertEqual(MovimientoInventario.objects.count(), 0)
        self.assertContains(r, "ya coincide")

    def test_cantidades_invalidas_rechazadas_sin_cambios(self):
        for tipo, cantidad in [("reposicion", "0"), ("reposicion", "-5"), ("ajuste", "-1"),
                               ("reposicion", "abc"), ("reposicion", ""), ("ajuste", "1.234"),
                               ("reposicion", "nan"), ("reposicion", "1e400"), ("otro", "10")]:
            r = self.enviar(tipo, cantidad)
            self.assertEqual(r.status_code, 200, (tipo, cantidad))
            self.assertEqual(self.ron.stock_actual, Decimal("500"), (tipo, cantidad))
        self.assertEqual(MovimientoInventario.objects.count(), 0)

    def test_reposicion_se_registra_como_compra(self):
        r = self.enviar("reposicion", "750", costo="16")
        c = Compra.objects.get(); d = DetalleCompra.objects.get()
        self.assertEqual((c.usuario, c.total), (self.user, 12000))              # 750 × 16
        self.assertEqual((d.compra, d.insumo, d.cantidad, d.costo_unitario), (c, self.ron, Decimal("750"), Decimal("16")))
        self.assertIn(f"Compra #{c.pk}", MovimientoInventario.objects.get().motivo)
        self.assertContains(r, f"Compra #{c.pk} registrada (total $12.000)")
        self.assertEqual(self.ron.stock_actual, Decimal("1250"))

    def test_total_de_la_compra_se_redondea_a_pesos_enteros(self):
        self.enviar("reposicion", "3", costo="0.5")      # 1,5 -> 2
        self.assertEqual(Compra.objects.get().total, 2)

    def test_costo_cero_es_valido(self):
        self.enviar("reposicion", "100", costo="0")
        self.assertEqual(Compra.objects.get().total, 0)

    def test_reposicion_sin_costo_o_con_costo_invalido_se_rechaza_sin_cambios(self):
        for costo in (None, "", "-1", "abc", "1.234", "nan", "1e400"):
            self.enviar("reposicion", "100", costo=costo)
            self.assertEqual(self.ron.stock_actual, Decimal("500"), costo)
        self.assertEqual((Compra.objects.count(), DetalleCompra.objects.count(), MovimientoInventario.objects.count()), (0, 0, 0))

    def test_total_demasiado_grande_rechazado(self):
        r = self.enviar("reposicion", "1000000", costo="5000")      # 5.000 millones > límite de la base
        self.assertContains(r, "demasiado grande")
        self.assertEqual(Compra.objects.count(), 0)

    def test_ajuste_por_conteo_no_es_una_compra_ni_pide_costo(self):
        self.enviar("ajuste", "420", costo=None)
        self.assertEqual(self.ron.stock_actual, Decimal("420"))
        self.assertEqual((Compra.objects.count(), MovimientoInventario.objects.count()), (0, 1))

    def test_insumo_inexistente(self):
        r = self.client.post(reverse("stock"), {"licor": 9999, "tipo": "reposicion", "cantidad": "5", "costo_unitario": "1"}, follow=True)
        self.assertContains(r, "no existe")

    def test_refrescar_no_repite_la_operacion(self):
        self.enviar("reposicion", "100")
        self.client.get(reverse("stock")); self.client.get(reverse("stock"))
        self.ron.refresh_from_db()
        self.assertEqual(self.ron.stock_actual, Decimal("600"))
