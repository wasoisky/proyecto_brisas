from django.contrib import messages
from django.db import models
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import ListView, CreateView, UpdateView

from .forms import UsuarioCreateForm, UsuarioUpdateForm, AdminPasswordResetForm
from .mixins import RolRequiredMixin, SOLO_ADMIN
from .models import Usuario, RegistroAcceso


class UsuarioListView(RolRequiredMixin, ListView):
    roles_permitidos = SOLO_ADMIN
    model = Usuario
    template_name = 'usuarios/lista.html'
    context_object_name = 'usuarios'
    paginate_by = 10

    def get_queryset(self):
        qs = Usuario.objects.exclude(is_superuser=True).order_by('rol', 'last_name', 'first_name')
        if q := self.request.GET.get('q'):
            qs = qs.filter(
                models.Q(username__icontains=q) |
                models.Q(first_name__icontains=q) |
                models.Q(last_name__icontains=q)
            )
        if rol := self.request.GET.get('rol'):
            qs = qs.filter(rol=rol)
        activo = self.request.GET.get('activo')
        if activo in ('1', '0'):
            qs = qs.filter(is_active=activo == '1')
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['roles'] = Usuario.Rol.choices
        return ctx


class UsuarioCreateView(RolRequiredMixin, CreateView):
    roles_permitidos = SOLO_ADMIN
    model = Usuario
    form_class = UsuarioCreateForm
    template_name = 'usuarios/form.html'
    success_url = reverse_lazy('usuarios:lista')

    def form_valid(self, form):
        usuario = form.save()
        messages.success(self.request, f'Usuario "{usuario.username}" creado correctamente.')
        return redirect(self.success_url)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = 'Nuevo usuario'
        return ctx


class UsuarioUpdateView(RolRequiredMixin, UpdateView):
    roles_permitidos = SOLO_ADMIN
    model = Usuario
    form_class = UsuarioUpdateForm
    template_name = 'usuarios/form.html'
    success_url = reverse_lazy('usuarios:lista')

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        if obj.is_superuser:
            messages.error(self.request, 'No se puede editar un superusuario desde aquí.')
            return None
        return obj

    def get(self, request, *args, **kwargs):
        if self.get_object() is None:
            return redirect('usuarios:lista')
        return super().get(request, *args, **kwargs)

    def form_valid(self, form):
        usuario = form.save(commit=False)
        if usuario.pk == self.request.user.pk and not form.cleaned_data.get('is_active', True):
            messages.error(self.request, 'No puedes desactivar tu propia cuenta.')
            return self.form_invalid(form)
        if usuario.pk == self.request.user.pk and form.cleaned_data.get('rol') != 'ADMIN':
            messages.error(self.request, 'No puedes cambiar tu propio rol.')
            form.add_error('rol', 'No puedes cambiar tu propio rol.')
            return self.form_invalid(form)
        usuario.save()
        messages.success(self.request, f'Usuario "{usuario.username}" actualizado.')
        return redirect(self.success_url)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = f'Editar usuario — {self.object.username}'
        return ctx


class UsuarioSetPasswordView(RolRequiredMixin, View):
    roles_permitidos = SOLO_ADMIN

    def _get_usuario(self, pk):
        return get_object_or_404(Usuario, pk=pk, is_superuser=False)

    def get(self, request, pk):
        usuario = self._get_usuario(pk)
        form = AdminPasswordResetForm()
        return render(request, 'usuarios/password_form.html', {'form': form, 'usuario': usuario})

    def post(self, request, pk):
        usuario = self._get_usuario(pk)
        form = AdminPasswordResetForm(request.POST)
        if form.is_valid():
            usuario.set_password(form.cleaned_data['password1'])
            usuario.save()
            messages.success(request, f'Contraseña de "{usuario.username}" actualizada correctamente.')
            return redirect('usuarios:lista')
        return render(request, 'usuarios/password_form.html', {'form': form, 'usuario': usuario})


class UsuarioToggleActivoView(RolRequiredMixin, View):
    roles_permitidos = SOLO_ADMIN

    def post(self, request, pk):
        usuario = get_object_or_404(Usuario, pk=pk, is_superuser=False)
        if usuario.pk == request.user.pk:
            messages.error(request, 'No puedes desactivar tu propia cuenta.')
            return redirect('usuarios:lista')
        usuario.is_active = not usuario.is_active
        usuario.save(update_fields=['is_active'])
        estado = 'activado' if usuario.is_active else 'desactivado'
        messages.success(request, f'Usuario "{usuario.username}" {estado}.')
        return redirect('usuarios:lista')


class RegistroAccesoListView(RolRequiredMixin, ListView):
    roles_permitidos = SOLO_ADMIN
    model = RegistroAcceso
    template_name = 'usuarios/accesos.html'
    context_object_name = 'registros'
    paginate_by = 10

    def get_queryset(self):
        qs = RegistroAcceso.objects.select_related('usuario').order_by('-timestamp')
        if accion := self.request.GET.get('accion'):
            qs = qs.filter(accion=accion)
        if usuario := self.request.GET.get('usuario'):
            qs = qs.filter(username_intento__icontains=usuario)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['acciones'] = RegistroAcceso.Accion.choices
        return ctx
