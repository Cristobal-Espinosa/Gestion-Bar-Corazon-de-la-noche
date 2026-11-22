from django.db import transaction

from carta.models import Coctel
from inventario.models import Insumo, MovimientoInventario
from inventario.services import TIPO_VENTA, ErrorDeNegocio, formato, tipo_movimiento

from .models import DetalleVenta, Venta

MAX_CANTIDAD = 1000


class StockInsuficiente(ErrorDeNegocio):
    pass


@transaction.atomic
def registrar_venta(usuario, coctel_id, cantidad):
    """Registra la venta y descuenta el stock según la receta. Todo o nada.

    Crea: Venta + DetalleVenta (con el precio vigente) + un MovimientoInventario
    negativo por cada insumo de la receta. Si algún insumo no alcanza, no cambia nada.
    """
    try:
        coctel = Coctel.objects.get(pk=coctel_id, visible=True)
    except (Coctel.DoesNotExist, ValueError, TypeError):
        raise ErrorDeNegocio("El cóctel seleccionado no existe.")

    recetas = list(coctel.recetas.select_related("insumo"))
    if not recetas:
        raise ErrorDeNegocio(f"{coctel.nombre} no tiene receta cargada, no se puede descontar stock.")

    # Bloquea las filas de los insumos: dos ventas simultáneas no pueden gastar el mismo stock.
    insumos = {i.pk: i for i in Insumo.objects.select_for_update().filter(pk__in=[r.insumo_id for r in recetas])}

    faltan = []
    for r in recetas:
        insumo = insumos[r.insumo_id]
        necesario = r.cantidad * cantidad
        if insumo.stock_actual < necesario:
            unidad = insumo.get_unidad_medida_display()
            faltan.append(f"{insumo.nombre} (necesita {formato(necesario)} {unidad}, hay {formato(insumo.stock_actual)})")
    if faltan:
        raise StockInsuficiente("Venta bloqueada. Falta stock de: " + "; ".join(faltan) + ".")

    venta = Venta.objects.create(usuario=usuario)
    DetalleVenta.objects.create(venta=venta, coctel=coctel, cantidad=cantidad, precio_unitario=coctel.precio)

    tipo = tipo_movimiento(TIPO_VENTA)
    for r in recetas:
        insumo = insumos[r.insumo_id]
        necesario = r.cantidad * cantidad
        insumo.stock_actual -= necesario
        insumo.save(update_fields=["stock_actual"])
        MovimientoInventario.objects.create(
            insumo=insumo, usuario=usuario, tipo_movimiento=tipo, cantidad=-necesario,
            motivo=f"Venta #{venta.pk}: {cantidad} × {coctel.nombre}",
        )
    return venta, coctel
