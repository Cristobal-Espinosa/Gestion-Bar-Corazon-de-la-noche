from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path

urlpatterns = [
    # El login NO aparece en el menú público: se entra escribiendo /ingresar/ o con un enlace directo.
    path(
        "ingresar/",
        LoginView.as_view(template_name="inventario/login.html", redirect_authenticated_user=True),
        name="login",
    ),
    # Cerrar sesión exige POST (desde Django 5): en el HTML va como formulario, no como enlace.
    path("salir/", LogoutView.as_view(), name="logout"),
]
