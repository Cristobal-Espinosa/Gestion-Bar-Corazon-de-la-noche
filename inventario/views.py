from django.shortcuts import render

from .models import Insumo


def inicio(request):
    return render(request, "inventario/index.html")


def stock(request):
    contexto = {}
    if request.method == "POST":
        # Reposición y ajuste de stock: sprint siguiente.
        contexto = {"mensaje": "El ajuste de stock se habilitará en el próximo sprint.", "tipo": "warning"}
    licores = [
        {
            "id": i.id,
            "nombre": i.nombre,
            "stock_ml": i.stock_actual,   # el template usa este nombre
            "unidad": i.unidad_medida,
            "unidad_label": i.get_unidad_medida_display(),
            "porcentaje": i.porcentaje,
            "bajo_minimo": i.bajo_minimo,
        }
        for i in Insumo.objects.select_related("categoria")
    ]
    contexto["licores"] = licores
    return render(request, "inventario/stock.html", contexto)
