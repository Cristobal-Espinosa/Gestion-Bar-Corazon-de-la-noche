from django.shortcuts import render

from .models import CategoriaCoctel, Coctel
from .services import disponibilidad


def _categoria_seleccionada(request):
    """Categoría pedida con ?categoria=<id>. Si falta o no es válida, equivale a "Todas"."""
    valor = request.GET.get("categoria", "")
    if valor.isascii() and valor.isdigit() and len(valor) <= 9:
        return CategoriaCoctel.objects.filter(pk=int(valor)).first()
    return None


def catalogo(request):
    categoria_sel = _categoria_seleccionada(request)
    cocteles = (
        Coctel.objects.filter(visible=True)
        .select_related("categoria")
        .prefetch_related("recetas__insumo")
    )
    if categoria_sel:
        cocteles = cocteles.filter(categoria=categoria_sel)
    items = []
    for c in cocteles:
        disponible, faltan = disponibilidad(c)
        items.append({"obj": c, "disponible": disponible, "faltan": faltan})
    contexto = {
        "cocteles": items,
        "categorias": CategoriaCoctel.objects.all(),   # todas, tengan o no cócteles visibles
        "categoria_sel": categoria_sel,                # None = "Todas"
    }
    return render(request, "inventario/menu.html", contexto)
