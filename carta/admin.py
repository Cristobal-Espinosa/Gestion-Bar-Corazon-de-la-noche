from django.contrib import admin

from .models import CategoriaCoctel, Coctel, RecetaCoctel
from .services import disponibilidad


class RecetaInline(admin.TabularInline):
    model = RecetaCoctel
    extra = 1
    min_num = 1            # un cóctel sin receta no tiene cómo calcular su disponibilidad

    def get_formset(self, request, obj=None, **kwargs):
        kwargs["validate_min"] = True   # exige al menos un ingrediente al guardar
        return super().get_formset(request, obj, **kwargs)


@admin.register(Coctel)
class CoctelAdmin(admin.ModelAdmin):
    list_display = ("nombre", "categoria", "precio", "visible", "disponible_ahora")
    list_filter = ("categoria", "visible")
    search_fields = ("nombre",)
    inlines = [RecetaInline]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("categoria").prefetch_related("recetas__insumo")

    @admin.display(boolean=True, description="Disponible (según stock)")
    def disponible_ahora(self, obj):
        return disponibilidad(obj)[0]


admin.site.register(CategoriaCoctel)
