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


class RegistroAuditoria(models.Model):
    """Bitácora de operaciones (RS-03): quién creó, modificó o eliminó qué y cuándo.

    Se llena automáticamente por señales (usuarios/auditoria.py) para todos los modelos
    de negocio; nadie la edita ni la borra desde el sistema.
    """
    class Accion(models.TextChoices):
        CREAR = 'CRE', 'Creación'
        MODIFICAR = 'MOD', 'Modificación'
        ELIMINAR = 'ELI', 'Eliminación'

    fecha_hora = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Fecha y hora')
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='registros_auditoria',
    )
    usuario_nombre = models.CharField(
        max_length=150, blank=True,
        help_text='Nombre de usuario al momento de la operación (vacío si la hizo el sistema).',
    )
    accion = models.CharField(max_length=3, choices=Accion.choices, verbose_name='Operación')
    modelo = models.CharField(max_length=100, db_index=True, help_text='app.Modelo, p. ej. distribucion.Entrega')
    objeto_id = models.CharField(max_length=40, verbose_name='ID del registro')
    descripcion = models.CharField(max_length=255, blank=True)
    cambios = models.JSONField(default=dict, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        verbose_name = 'Registro de Auditoría'
        verbose_name_plural = 'Registros de Auditoría'
        ordering = ['-fecha_hora', '-id']

    def __str__(self):
        return f'{self.fecha_hora:%Y-%m-%d %H:%M} — {self.get_accion_display()} — {self.modelo} #{self.objeto_id}'

    def _clase_modelo(self):
        from django.apps import apps
        try:
            return apps.get_model(self.modelo)
        except (LookupError, ValueError):
            return None

    def get_modelo_display(self):
        clase = self._clase_modelo()
        if clase is None:
            return self.modelo
        etiqueta = str(clase._meta.verbose_name)
        return etiqueta[:1].upper() + etiqueta[1:]

    @property
    def cambios_legibles(self):
        """Lista de (campo, antes, después) en modificaciones; (campo, valor, '') en el resto."""
        clase = self._clase_modelo()
        filas = []
        for campo, valor in (self.cambios or {}).items():
            nombre = campo
            if clase is not None:
                for f in clase._meta.concrete_fields:
                    if f.attname == campo:
                        etiqueta = str(f.verbose_name)
                        nombre = etiqueta[:1].upper() + etiqueta[1:]
                        break
            if self.accion == self.Accion.MODIFICAR and isinstance(valor, list) and len(valor) == 2:
                filas.append((nombre, str(valor[0]), str(valor[1])))
            else:
                filas.append((nombre, str(valor), ''))
        return filas