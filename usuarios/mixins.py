from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect

# URL de inicio según rol — destino cuando se bloquea acceso
INICIO_POR_ROL = {
    'ADMIN': '/produccion/productos/',
    'PROD':  '/produccion/registro/',
    'DIST':  '/distribucion/ruta/',
}

TODOS  = ['ADMIN', 'PROD', 'DIST']
ADMIN_PROD = ['ADMIN', 'PROD']
SOLO_ADMIN = ['ADMIN']
ADMIN_DIST = ['ADMIN', 'DIST']


class RolRequiredMixin(LoginRequiredMixin):
    """
    Reemplaza LoginRequiredMixin en todas las vistas del proyecto.
    Declara `roles_permitidos` en cada vista para controlar el acceso.
    Los superusuarios técnicos (is_superuser) siempre tienen acceso.
    """
    roles_permitidos: list[str] = []

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if request.user.is_superuser or request.user.rol in self.roles_permitidos:
            return super().dispatch(request, *args, **kwargs)
        messages.error(request, 'No tienes permiso para acceder a esta sección.')
        destino = INICIO_POR_ROL.get(request.user.rol, '/')
        return redirect(destino)
