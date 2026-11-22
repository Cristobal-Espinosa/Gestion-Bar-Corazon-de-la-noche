from django.shortcuts import render

from .models import Coctel
from .services import disponibilidad


def catalogo(request):
    cocteles = (
        Coctel.objects.filter(visible=True)
        .select_related("categoria")
        .prefetch_related("recetas__insumo")
    )
    items = []
    for c in cocteles:
        disponible, faltan = disponibilidad(c)
        items.append({"obj": c, "disponible": disponible, "faltan": faltan})
    return render(request, "inventario/menu.html", {"cocteles": items})
