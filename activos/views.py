from datetime import date

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from usuarios.mixins import RolRequiredMixin, ADMIN_PROD
from django.urls import reverse_lazy
from django.views.generic import TemplateView, ListView, CreateView, DetailView

from reportes.cierres import anio_cerrado
from .models import ActivoRetornable, MovimientoActivo
from .forms import BajaActivoForm, MovimientoActivoForm


class ActivosDashboardView(RolRequiredMixin, TemplateView):
    roles_permitidos = ADMIN_PROD
    template_name = 'activos/dashboard.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        resumen = []
        for tipo_val, tipo_label in ActivoRetornable.TipoActivo.choices:
            ultimo = (
                MovimientoActivo.objects
                .filter(tipo_activo=tipo_val)
                .order_by('-fecha', '-creado_en')
                .first()
            )
            resumen.append({
                'tipo': tipo_val,
                'label': tipo_label,
                'ultimo': ultimo,
            })

        ctx['resumen'] = resumen
        ctx['recientes'] = MovimientoActivo.objects.select_related('registrado_por')[:10]
        ctx['hoy'] = date.today()
        return ctx


class MovimientoListView(RolRequiredMixin, ListView):
    roles_permitidos = ADMIN_PROD
    model = MovimientoActivo
    template_name = 'activos/movimiento_list.html'
    context_object_name = 'movimientos'
    paginate_by = 10

    def get_queryset(self):
        qs = MovimientoActivo.objects.select_related('registrado_por')
        if fecha := self.request.GET.get('fecha'):
            qs = qs.filter(fecha=fecha)
        if tipo := self.request.GET.get('tipo_activo'):
            qs = qs.filter(tipo_activo=tipo)
        if momento := self.request.GET.get('momento'):
            qs = qs.filter(momento=momento)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['tipos'] = ActivoRetornable.TipoActivo.choices
        ctx['momentos'] = MovimientoActivo.Momento.choices
        return ctx


class MovimientoCreateView(RolRequiredMixin, CreateView):
    roles_permitidos = ADMIN_PROD
    model = MovimientoActivo
    form_class = MovimientoActivoForm
    template_name = 'activos/movimiento_form.html'
    success_url = reverse_lazy('activos:dashboard')

    def get_initial(self):
        return {'fecha': date.today()}

    def form_valid(self, form):
        form.instance.registrado_por = self.request.user
        tipo = form.instance.get_tipo_activo_display()
        momento = form.instance.get_momento_display()
        messages.success(self.request, f'Movimiento registrado: {tipo} — {momento}.')
        return super().form_valid(form)


class MovimientoDetailView(RolRequiredMixin, DetailView):
    roles_permitidos = ADMIN_PROD
    model = MovimientoActivo
    template_name = 'activos/movimiento_detail.html'
    context_object_name = 'mov'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['bajas'] = self.object.bajas.select_related('registrado_por')
        ctx['baja_form'] = BajaActivoForm()
        return ctx


class BajaActivoCreateView(RolRequiredMixin, CreateView):
    roles_permitidos = ADMIN_PROD
    form_class = BajaActivoForm

    def get_movimiento(self):
        return get_object_or_404(MovimientoActivo, pk=self.kwargs['movimiento_pk'])

    def dispatch(self, request, *args, **kwargs):
        movimiento = self.get_movimiento()
        if anio_cerrado(movimiento.fecha.year):
            messages.error(
                request,
                f'El año {movimiento.fecha.year} ya está cerrado; no se pueden registrar bajas.',
            )
            return redirect('activos:movimiento_detail', pk=self.kwargs['movimiento_pk'])
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.movimiento = self.get_movimiento()
        form.instance.registrado_por = self.request.user
        messages.success(self.request, 'Baja registrada.')
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, 'No se pudo registrar la baja: revisa los datos.')
        return redirect('activos:movimiento_detail', pk=self.kwargs['movimiento_pk'])

    def get_success_url(self):
        return reverse_lazy('activos:movimiento_detail', kwargs={'pk': self.kwargs['movimiento_pk']})
