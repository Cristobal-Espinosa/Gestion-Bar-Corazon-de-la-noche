"""Reglas de negocio del stock (sin HTML ni request): se pueden probar por separado."""
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from django.db import transaction

from .models import Compra, DetalleCompra, Insumo, MovimientoInventario, TipoMovimiento

TIPO_VENTA = "Venta"
TIPO_REPOSICION = "Reposición"
TIPO_AJUSTE = "Ajuste por conteo físico"

MAX_STOCK = Decimal("99999999.99")   # límite de la columna (10 dígitos, 2 decimales)
MAX_TOTAL = 2_147_483_647            # límite de Compra.total (entero de la base de datos)


class ErrorDeNegocio(Exception):
    """Error que se le muestra tal cual a quien usa la página."""


def formato(valor):
    """Decimal sin ceros sobrantes: 500.00 -> '500', 2.50 -> '2.5'."""
    valor = Decimal(valor)
    texto = format(valor.normalize(), "f")
    return texto


def tipo_movimiento(nombre):
    """Obtiene (o crea la primera vez) el tipo de movimiento por su nombre."""
    return TipoMovimiento.objects.get_or_create(nombre=nombre)[0]


def parsear_decimal(texto, nombre="cantidad"):
    """Convierte lo que escribió la persona en Decimal (máx. 2 decimales)."""
    if not str(texto).strip():
        raise ErrorDeNegocio(f"Ingresa {nombre}.")
    try:
        valor = Decimal(str(texto).strip())
    except (InvalidOperation, ValueError):
        raise ErrorDeNegocio(f"Ingresa {nombre} como número.")
    if not valor.is_finite():
        raise ErrorDeNegocio(f"Ingresa {nombre} como número.")
    if abs(valor) > MAX_STOCK:
        raise ErrorDeNegocio(f"El valor de {nombre} es demasiado grande.")
    if valor != valor.quantize(Decimal("0.01")):
        raise ErrorDeNegocio("Usa como máximo 2 decimales.")
    return valor


def parsear_cantidad(texto):
    return parsear_decimal(texto, "una cantidad")


def parsear_costo(texto):
    return parsear_decimal(texto, "el costo por unidad")


@transaction.atomic
def ajustar_stock(usuario, insumo_id, tipo, cantidad, costo_unitario=None):
    """Reposición (suma, se registra como COMPRA) o ajuste por conteo físico (fija el stock).

    Guarda siempre un MovimientoInventario con la diferencia (positiva o negativa).
    La reposición además crea Compra + DetalleCompra; el total lo calcula el sistema
    (cantidad × costo unitario). Devuelve (insumo, movimiento, compra); movimiento es None
    si el conteo coincide con el stock y compra es None salvo en reposiciones.
    """
    try:
        insumo = Insumo.objects.select_for_update().get(pk=insumo_id)
    except (Insumo.DoesNotExist, ValueError, TypeError):
        raise ErrorDeNegocio("El insumo seleccionado no existe.")

    actual = insumo.stock_actual
    if tipo == "reposicion":
        if cantidad <= 0:
            raise ErrorDeNegocio("La reposición debe ser mayor que 0.")
        if costo_unitario is None:
            raise ErrorDeNegocio("Ingresa el costo por unidad.")
        if costo_unitario < 0:
            raise ErrorDeNegocio("El costo por unidad no puede ser negativo.")
        total = int((cantidad * costo_unitario).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        if total > MAX_TOTAL:
            raise ErrorDeNegocio("El total de la compra es demasiado grande.")
        nuevo = actual + cantidad
        nombre_tipo, motivo = TIPO_REPOSICION, "Reposición de stock"
    elif tipo == "ajuste":
        if cantidad < 0:
            raise ErrorDeNegocio("El stock contado no puede ser negativo.")
        nuevo = cantidad
        nombre_tipo = TIPO_AJUSTE
        motivo = f"Ajuste por conteo físico (de {formato(actual)} a {formato(nuevo)})"
    else:
        raise ErrorDeNegocio("Tipo de cambio no válido.")

    if nuevo > MAX_STOCK:
        raise ErrorDeNegocio("El stock resultante supera el máximo permitido.")

    diferencia = nuevo - actual
    if diferencia == 0:
        return insumo, None, None   # nada que registrar (un movimiento de 0 no está permitido)

    compra = None
    if tipo == "reposicion":
        # La compra se crea primero: su detalle depende de ella.
        compra = Compra.objects.create(usuario=usuario, total=total)
        DetalleCompra.objects.create(compra=compra, insumo=insumo, cantidad=cantidad, costo_unitario=costo_unitario)
        motivo = f"Reposición de stock (Compra #{compra.pk})"

    insumo.stock_actual = nuevo
    insumo.save(update_fields=["stock_actual"])
    movimiento = MovimientoInventario.objects.create(
        insumo=insumo, usuario=usuario, tipo_movimiento=tipo_movimiento(nombre_tipo),
        cantidad=diferencia, motivo=motivo,
    )
    return insumo, movimiento, compra
