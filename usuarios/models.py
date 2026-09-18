from django.contrib.auth.models import AbstractUser
from django.conf import settings
from django.db import models


class Usuario(AbstractUser):
    """
    Usuario del sistema, hereda todo lo de Django (username, password,
    email, etc.) y le agregamos el rol.
    El control de permisos por rol (RBAC) se apoya en los Groups de Django.
    """
    class Rol(models.TextChoices):
        ADMINISTRADOR = 'ADMIN', 'Administrador'
        PRODUCCION = 'PROD', 'Operario de Producción'
        DISTRIBUCION = 'DIST', 'Operario de Distribución'

    rol = models.CharField(
        max_length=10,
        choices=Rol.choices,
        default=Rol.ADMINISTRADOR,
        verbose_name='Rol del usuario'
    )
    telefono = models.CharField(max_length=20, blank=True, null=True, verbose_name='Teléfono')

    def __str__(self):
        return f'{self.username} ({self.get_rol_display()})'


class RegistroAcceso(models.Model):
    class Accion(models.TextChoices):
        LOGIN_OK      = 'LOGIN',  'Inicio de sesión'
        LOGOUT        = 'LOGOUT', 'Cierre de sesión'
        LOGIN_FALLIDO = 'FALLO',  'Intento fallido'

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='registros_acceso',
    )
    username_intento = models.CharField(max_length=150, blank=True)
    accion = models.CharField(max_length=6, choices=Accion.choices)
    ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=300, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Registro de Acceso'
        verbose_name_plural = 'Registros de Acceso'
        ordering = ['-timestamp']

    def __str__(self):
        quien = self.username_intento or (self.usuario.username if self.usuario else '?')
        return f'{self.timestamp:%Y-%m-%d %H:%M} — {self.get_accion_display()} — {quien}'