from django.contrib import admin

from .models import (CategoriaInsumo, Compra, DetalleCompra, Insumo,
                     MovimientoInventario, TipoMovimiento)


@admin.register(Insumo)
class InsumoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "categoria", "stock_actual", "stock_minimo", "unidad_medida", "bajo_minimo")
    list_filter = ("categoria", "unidad_medida")
    search_fields = ("nombre",)

    @admin.display(boolean=True, description="En/bajo el mínimo")
    def bajo_minimo(self, obj):
        return obj.bajo_minimo


class DetalleCompraInline(admin.TabularInline):
    model = DetalleCompra
    extra = 1


@admin.register(Compra)
class CompraAdmin(admin.ModelAdmin):
    list_display = ("id", "fecha", "usuario", "total")
    inlines = [DetalleCompraInline]


admin.site.register(CategoriaInsumo)
admin.site.register(TipoMovimiento)
admin.site.register(MovimientoInventario)
