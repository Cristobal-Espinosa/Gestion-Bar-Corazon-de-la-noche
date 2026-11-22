def disponibilidad(coctel):
    """Devuelve (disponible, faltan) calculado con el stock actual.

    Un cóctel está disponible si tiene receta y TODOS sus insumos alcanzan
    para una preparación. `faltan` lista los insumos insuficientes.
    """
    recetas = list(coctel.recetas.all())  # usa prefetch si existe
    faltan = [r.insumo.nombre for r in recetas if r.insumo.stock_actual < r.cantidad]
    return (bool(recetas) and not faltan), faltan
