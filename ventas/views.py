from django.shortcuts import render

from carta.models import Coctel


def venta(request):
    # Registro de ventas: sprint siguiente. La página ya existe para que la navegación no falle.
    contexto = {"cocteles": Coctel.objects.filter(visible=True)}
    if request.method == "POST":
        contexto.update(mensaje="El registro de ventas se habilitará en el próximo sprint.", tipo="warning")
    return render(request, "inventario/venta.html", contexto)
