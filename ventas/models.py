from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone


class Venta(models.Model):
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="ventas")
    fecha = models.DateField("fecha", default=timezone.localdate)

    class Meta:
        db_table = "bcdln_venta"
        verbose_name = "venta"
        verbose_name_plural = "ventas"
        ordering = ["-fecha", "-id"]

    def __str__(self):
        return f"Venta #{self.pk} ({self.fecha})"


class DetalleVenta(models.Model):
    venta = models.ForeignKey(Venta, on_delete=models.CASCADE, related_name="detalles")
    coctel = models.ForeignKey("carta.Coctel", on_delete=models.PROTECT, related_name="detalles_venta")
    cantidad = models.IntegerField(
        "cantidad", validators=[MinValueValidator(1, "La cantidad vendida debe ser mayor que 0.")]
    )
    precio_unitario = models.IntegerField(
        "precio unitario", validators=[MinValueValidator(0, "El precio unitario no puede ser negativo.")]
    )

    class Meta:
        db_table = "bcdln_detalle_venta"
        verbose_name = "detalle de venta"
        verbose_name_plural = "detalles de venta"
        constraints = [
            models.UniqueConstraint(
                fields=["venta", "coctel"], name="uq_detalle_venta_venta_coctel",
                violation_error_message="Este cóctel ya está en esta venta.",
            ),
            models.CheckConstraint(condition=Q(cantidad__gt=0), name="ck_detalle_venta_cantidad_mayor_0"),
            models.CheckConstraint(condition=Q(precio_unitario__gte=0), name="ck_detalle_venta_precio_no_negativo"),
        ]

    def __str__(self):
        return f"{self.venta} · {self.coctel}"
