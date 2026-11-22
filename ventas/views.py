from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from carta.models import Coctel
from inventario import flash
from inventario.services import ErrorDeNegocio

from .services import MAX_CANTIDAD, registrar_venta


@login_required
def venta(request):
    contexto = {}
    if request.method == "POST":
        coctel_sel = request.POST.get("coctel", "")
        texto = request.POST.get("cantidad", "").strip()
        try:
            cantidad = int(texto)
        except ValueError:
            cantidad = None
        if cantidad is None or cantidad < 1:
            error = "La cantidad debe ser al menos 1"
        elif cantidad > MAX_CANTIDAD:
            error = f"La cantidad máxima por venta es {MAX_CANTIDAD}"
        else:
            error = None

        if error:
            contexto.update(coctel_sel=coctel_sel, cantidad=texto, error_cantidad=error)
        else:
            try:
                v, coctel = registrar_venta(request.user, coctel_sel, cantidad)
            except ErrorDeNegocio as e:
                # Se vuelve a mostrar el formulario con lo que la persona había ingresado.
                contexto.update(coctel_sel=coctel_sel, cantidad=cantidad, mensaje=str(e), tipo="danger")
            else:
                total = coctel.precio * cantidad
                flash.guardar(
                    request,
                    f"Venta #{v.pk} registrada: {cantidad} × {coctel.nombre} (${total:,}). Stock descontado.".replace(",", "."),
                    "success",
                )
                return redirect("venta")   # Post/Redirect/Get: refrescar no repite la venta

    if "mensaje" not in contexto:
        contexto.update(flash.sacar(request))
    contexto["cocteles"] = Coctel.objects.filter(visible=True).order_by("nombre")
    return render(request, "inventario/venta.html", contexto)
