from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("inventario.urls")),   # inicio, stock
    path("", include("carta.urls")),        # catalogo
    path("", include("ventas.urls")),       # venta
    path("", include("usuarios.urls")),
]

if settings.DEBUG:  # imágenes subidas desde el admin (solo desarrollo)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
