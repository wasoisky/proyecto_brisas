from django.apps import AppConfig


class UsuariosConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'usuarios'

    def ready(self):
        import usuarios.signals  # noqa: F401 — conecta las señales al iniciar
        from . import auditoria
        auditoria.conectar()  # bitácora de operaciones (RS-03)
