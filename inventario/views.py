from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from . import flash
from .models import Insumo
from .services import ErrorDeNegocio, ajustar_stock, estado_reposicion, formato, parsear_cantidad, parsear_costo


def inicio(request):
    # Portada del sistema: solo trabajadores. Quien no inició sesión ve la carta.
    if not request.user.is_authenticated:
        return redirect("catalogo")
    return render(request, "inventario/index.html")


@login_required
def stock(request):
    if request.method == "POST":
        try:
            tipo_cambio = request.POST.get("tipo")
            cantidad = parsear_cantidad(request.POST.get("cantidad", ""))
            # El costo solo se pide al reponer (la reposición se registra como compra).
            costo = parsear_costo(request.POST.get("costo_unitario", "")) if tipo_cambio == "reposicion" else None
            insumo, movimiento, compra = ajustar_stock(
                request.user, request.POST.get("licor"), tipo_cambio, cantidad, costo
            )
        except ErrorDeNegocio as error:
            mensaje, tipo = str(error), "danger"
        else:
            unidad = insumo.get_unidad_medida_display()
            if movimiento is None:
                mensaje, tipo = f"El stock de {insumo.nombre} ya coincide con el conteo; no se registró ningún cambio.", "info"
            else:
                mensaje = f"Stock de {insumo.nombre} actualizado: ahora hay {formato(insumo.stock_actual)} {unidad}."
                if compra:
                    mensaje = f"Compra #{compra.pk} registrada (total ${compra.total:,}). ".replace(",", ".") + mensaje
                tipo = "success"
        flash.guardar(request, mensaje, tipo)
        return redirect("stock")          # Post/Redirect/Get

    # Se calcula en cada visita con el stock de ese momento: si el inventario cambia, la tabla también.
    licores = []
    for i in Insumo.objects.all():
        estado, faltan = estado_reposicion(i)
        licores.append(
            {
                "id": i.id,
                "nombre": i.nombre,
                "stock_ml": i.stock_actual,
                "unidad_label": i.get_unidad_medida_display(),
                "bajo_minimo": i.bajo_minimo,   # stock <= mínimo (pinta el stock en rojo)
                "minimo": i.stock_minimo,
                "estado": estado,               # "bajo" | "minimo" | "ok"
                "faltan": faltan,
            }
        )

    # Filtro por estado de stock (RF-07): ?estado=bajo_minimo | sin_stock. Cualquier otro valor equivale a "Todos".
    filtro_estado = request.GET.get("estado", "")
    if filtro_estado == "bajo_minimo":
        licores_tabla = [l for l in licores if l["bajo_minimo"]]          # stock <= mínimo
    elif filtro_estado == "sin_stock":
        licores_tabla = [l for l in licores if l["stock_ml"] == 0]        # stock en cero
    else:
        filtro_estado = ""
        licores_tabla = licores

    # "licores" sigue completa porque la usa el formulario "Actualizar stock"; la tabla usa "licores_tabla".
    return render(
        request,
        "inventario/stock.html",
        {"licores": licores, "licores_tabla": licores_tabla, "filtro_estado": filtro_estado, **flash.sacar(request)},
    )
