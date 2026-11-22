from django.contrib.auth.models import AbstractUser
from django.db import models


class Usuario(AbstractUser):
    """Usuario de Django con DOS apellidos (modelo de datos: bcdln_Usuario).

    Correspondencia con el diagrama:
      username   -> Username_usuario      first_name -> Nombre_usuario
      last_name  -> Apellido_1_usuario    apellido_2 -> Apellido_2_usuario
      email      -> Correo_usuario        password   -> Contraseña_usuario (hash)
      is_staff   -> is_staff_usuario      is_active  -> is_active_usuario
    """

    first_name = models.CharField("nombre", max_length=150)
    last_name = models.CharField("primer apellido", max_length=150)
    apellido_2 = models.CharField("segundo apellido", max_length=150)
    email = models.EmailField("correo electrónico", max_length=254)

    # Lo que pide `createsuperuser` además del username y la contraseña
    REQUIRED_FIELDS = ["email", "first_name", "last_name", "apellido_2"]

    class Meta:
        db_table = "bcdln_usuario"
        verbose_name = "usuario"
        verbose_name_plural = "usuarios"

    def __str__(self):
        return f"{self.first_name} {self.last_name} {self.apellido_2}".strip() or self.username
