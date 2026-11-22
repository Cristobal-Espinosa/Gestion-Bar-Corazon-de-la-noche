from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q


class CategoriaCoctel(models.Model):
    nombre = models.CharField(
        "nombre", max_length=20, unique=True,
        error_messages={"unique": "Ya existe una categoría de cóctel con ese nombre."},
    )

    class Meta:
        db_table = "bcdln_categoria_coctel"
        verbose_name = "categoría de cóctel"
        verbose_name_plural = "categorías de cóctel"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Coctel(models.Model):
    categoria = models.ForeignKey(
        CategoriaCoctel, on_delete=models.PROTECT, related_name="cocteles", verbose_name="categoría"
    )
    nombre = models.CharField(
        "nombre", max_length=100, unique=True,
        error_messages={"unique": "Ya existe un cóctel con ese nombre."},
    )
    descripcion = models.CharField("descripción", max_length=200, blank=True)
    precio = models.IntegerField(
        "precio de venta",
        validators=[MinValueValidator(0, "El precio de venta no puede ser negativo.")],
    )
    # Decisión del dueño del bar: si el cóctel aparece o no en la carta.
    # (La DISPONIBILIDAD no se guarda: se calcula con el stock.)
    visible = models.BooleanField("visible en la carta", default=True)
    imagen = models.ImageField("imagen", upload_to="cocteles/", max_length=200, blank=True)

    class Meta:
        db_table = "bcdln_coctel"
        verbose_name = "cóctel"
        verbose_name_plural = "cócteles"
        ordering = ["categoria__nombre", "nombre"]
        constraints = [
            models.CheckConstraint(condition=Q(precio__gte=0), name="ck_coctel_precio_no_negativo"),
        ]

    def __str__(self):
        return self.nombre


class RecetaCoctel(models.Model):
    coctel = models.ForeignKey(Coctel, on_delete=models.CASCADE, related_name="recetas", verbose_name="cóctel")
    insumo = models.ForeignKey("inventario.Insumo", on_delete=models.PROTECT, related_name="recetas")
    cantidad = models.IntegerField(
        "cantidad",
        validators=[MinValueValidator(1, "La cantidad del insumo en la receta debe ser mayor que 0.")],
    )

    class Meta:
        db_table = "bcdln_receta_coctel"
        verbose_name = "ingrediente de receta"
        verbose_name_plural = "receta"
        constraints = [
            # El diagrama usa PK compuesta (coctel, insumo): un insumo una sola vez por receta.
            models.UniqueConstraint(
                fields=["coctel", "insumo"], name="uq_receta_coctel_insumo",
                violation_error_message="Este insumo ya está en la receta de este cóctel.",
            ),
            models.CheckConstraint(condition=Q(cantidad__gt=0), name="ck_receta_cantidad_mayor_0"),
        ]

    def __str__(self):
        return f"{self.coctel}: {self.cantidad} de {self.insumo}"
