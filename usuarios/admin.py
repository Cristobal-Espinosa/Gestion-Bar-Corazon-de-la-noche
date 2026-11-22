from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Usuario


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (("Segundo apellido", {"fields": ("apellido_2",)}),)
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("Datos personales", {"fields": ("first_name", "last_name", "apellido_2", "email")}),
    )
    list_display = ("username", "first_name", "last_name", "apellido_2", "email", "is_staff", "is_active")
    search_fields = ("username", "first_name", "last_name", "apellido_2", "email")
