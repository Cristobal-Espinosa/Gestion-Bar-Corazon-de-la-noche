from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone


class CategoriaInsumo(models.Model):
    nombre = models.CharField(
        "nombre", max_length=50, unique=True,
        error_messages={"unique": "Ya existe una categoría de insumo con ese nombre."},
    )

    class Meta:
        db_table = "bcdln_categoria_insumo"
        verbose_name = "categoría de insumo"
        verbose_name_plural = "categorías de insumo"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Insumo(models.Model):
    """Licor, fruta u otro insumo. El nombre no se puede repetir."""

    UNIDADES = [("ml", "ml"), ("g", "g"), ("un", "unidades"), ("cdta", "cdta"), ("dash", "dash"), ("hojas", "hojas")]
    # Referencia para el % del stock: "lleno" = 3 veces el stock mínimo.
    # (El modelo no tiene capacidad de botella; ajustar si el grupo agrega un campo.)
    FACTOR_NIVEL_LLENO = 3

    categoria = models.ForeignKey(
        CategoriaInsumo, on_delete=models.PROTECT, related_name="insumos", verbose_name="categoría"
    )
    nombre = models.CharField(
        "nombre", max_length=50, unique=True,
        error_messages={"unique": "Ya existe un insumo con ese nombre."},
    )
    unidad_medida = models.CharField("unidad de medida", max_length=8, choices=UNIDADES, default="ml")
    stock_actual = models.DecimalField(
        "stock actual", max_digits=10, decimal_places=2, default=0,
        validators=[MinValueValidator(Decimal("0"), "El stock actual no puede ser negativo.")],
    )
    stock_minimo = models.DecimalField(
        "stock mínimo", max_digits=10, decimal_places=2, default=0,
        validators=[MinValueValidator(Decimal("1"), "El stock mínimo no puede ser menor a 1.")],
    )

    class Meta:
        db_table = "bcdln_insumo"
        verbose_name = "insumo"
        verbose_name_plural = "insumos"
        ordering = ["nombre"]
        constraints = [
            models.CheckConstraint(condition=Q(stock_actual__gte=0), name="ck_insumo_stock_actual_no_negativo"),
            models.CheckConstraint(condition=Q(stock_minimo__gte=0), name="ck_insumo_stock_minimo_no_negativo"),
        ]

    def __str__(self):
        return self.nombre

    @property
    def bajo_minimo(self):
        return self.stock_actual <= self.stock_minimo

    @property
    def porcentaje(self):
        """Nivel de stock de 0 a 100 (para la barra de stock.html)."""
        referencia = self.stock_minimo * self.FACTOR_NIVEL_LLENO
        if referencia <= 0:
            return 100 if self.stock_actual > 0 else 0
        return int(min(100, max(0, self.stock_actual / referencia * 100)))


class TipoMovimiento(models.Model):
    nombre = models.CharField(
        "nombre", max_length=100, unique=True,
        error_messages={"unique": "Ya existe un tipo de movimiento con ese nombre."},
    )

    class Meta:
        db_table = "bcdln_tipo_movimiento"
        verbose_name = "tipo de movimiento"
        verbose_name_plural = "tipos de movimiento"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class MovimientoInventario(models.Model):
    """Se usa desde el sprint siguiente (ajuste de stock). Ya queda migrado."""

    insumo = models.ForeignKey(Insumo, on_delete=models.PROTECT, related_name="movimientos")
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="movimientos")
    tipo_movimiento = models.ForeignKey(TipoMovimiento, on_delete=models.PROTECT, related_name="movimientos")
    # Supuesto a confirmar: positivo suma al stock, negativo resta (el tipo no trae signo).
    # cantidad = models.IntegerField("cantidad")
    cantidad = models.DecimalField("cantidad", max_digits=10, decimal_places=2)
    fecha = models.DateField("fecha", default=timezone.localdate)
    motivo = models.CharField("motivo", max_length=200, blank=True)

    class Meta:
        db_table = "bcdln_movimiento_inventario"
        verbose_name = "movimiento de inventario"
        verbose_name_plural = "movimientos de inventario"
        ordering = ["-fecha", "-id"]
        constraints = [
            models.CheckConstraint(condition=~Q(cantidad=0), name="ck_movimiento_cantidad_distinta_de_0"),
        ]

    def __str__(self):
        return f"{self.tipo_movimiento} · {self.insumo} · {self.cantidad}"


class Compra(models.Model):
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="compras")
    fecha = models.DateField("fecha", default=timezone.localdate)
    total = models.IntegerField(
        "total", default=0,
        validators=[MinValueValidator(0, "El total de la compra no puede ser negativo.")],
    )

    class Meta:
        db_table = "bcdln_compra"
        verbose_name = "compra"
        verbose_name_plural = "compras"
        ordering = ["-fecha", "-id"]
        constraints = [
            models.CheckConstraint(condition=Q(total__gte=0), name="ck_compra_total_no_negativo"),
        ]

    def __str__(self):
        return f"Compra #{self.pk} ({self.fecha})"


class DetalleCompra(models.Model):
    compra = models.ForeignKey(Compra, on_delete=models.CASCADE, related_name="detalles")
    insumo = models.ForeignKey(Insumo, on_delete=models.PROTECT, related_name="detalles_compra")
    cantidad = models.DecimalField(
        "cantidad", max_digits=10, decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"), "La cantidad comprada debe ser mayor que 0.")],
    )
    costo_unitario = models.DecimalField(
        "costo unitario", max_digits=10, decimal_places=2,
        validators=[MinValueValidator(Decimal("0"), "El costo unitario no puede ser negativo.")],
    )

    class Meta:
        db_table = "bcdln_detalle_compra"
        verbose_name = "detalle de compra"
        verbose_name_plural = "detalles de compra"
        constraints = [
            # El diagrama usa PK compuesta (compra, insumo); en Django se expresa así.
            models.UniqueConstraint(
                fields=["compra", "insumo"], name="uq_detalle_compra_compra_insumo",
                violation_error_message="Este insumo ya está en esta compra.",
            ),
            models.CheckConstraint(condition=Q(cantidad__gt=0), name="ck_detalle_compra_cantidad_mayor_0"),
            models.CheckConstraint(condition=Q(costo_unitario__gte=0), name="ck_detalle_compra_costo_no_negativo"),
        ]

    def __str__(self):
        return f"{self.compra} · {self.insumo}"
