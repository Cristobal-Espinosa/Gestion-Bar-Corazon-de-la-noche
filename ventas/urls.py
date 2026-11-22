from django.urls import path

from . import views

urlpatterns = [
    path("venta/", views.venta, name="venta"),
]
