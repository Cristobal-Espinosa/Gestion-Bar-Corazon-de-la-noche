"""Aviso de un solo uso que sobrevive a una redirección (patrón Post/Redirect/Get).

Evita que al refrescar la página después de registrar algo se repita el POST
(y, por ejemplo, se registre la venta dos veces).
"""


def guardar(request, mensaje, tipo):
    request.session["flash"] = {"mensaje": mensaje, "tipo": tipo}


def sacar(request):
    return request.session.pop("flash", None) or {}
