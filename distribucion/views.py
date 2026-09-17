import json
from datetime import date

from django.contrib import messages
from usuarios.mixins import RolRequiredMixin, SOLO_ADMIN, ADMIN_DIST
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import ListView, CreateView, UpdateView, DetailView

from produccion.models import Producto
from reportes.cierres import anio_cerrado
from .forms import ClienteForm, PlanillaForm, EntregaForm, AveriaForm
from .models import Cliente, PrecioPorCategoria, Planilla, Entrega, Averia, Credito


# ── Cliente ───────────────────────────────────────────────────────────────────

class ClienteListView(RolRequiredMixin, ListView):
    roles_permitidos = SOLO_ADMIN
    model = Cliente
    template_name = 'distribucion/cliente_list.html'
    context_object_name = 'clientes'
    paginate_by = 10

    def get_queryset(self):
        qs = Cliente.objects.all()
        if q := self.request.GET.get('q'):
            qs = qs.filter(nombre__icontains=q)
        if activo := self.request.GET.get('activo'):
            if activo in ('1', '0'):
                qs = qs.filter(activo=activo == '1')
        return qs


class ClienteCreateView(RolRequiredMixin, CreateView):
    roles_permitidos = SOLO_ADMIN
    model = Cliente
    form_class = ClienteForm
    template_name = 'distribucion/cliente_form.html'
    success_url = reverse_lazy('distribucion:cliente_list')

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f'Cliente "{self.object.nombre}" creado.')
        return response


class ClienteUpdateView(RolRequiredMixin, UpdateView):
    roles_permitidos = SOLO_ADMIN
    model = Cliente
    form_class = ClienteForm
    template_name = 'distribucion/cliente_form.html'
    success_url = reverse_lazy('distribucion:cliente_list')

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f'Cliente "{self.object.nombre}" actualizado.')
        return response


# ── Planilla (admin) ──────────────────────────────────────────────────────────

class PlanillaListView(RolRequiredMixin, ListView):
    roles_permitidos = SOLO_ADMIN
    model = Planilla
    template_name = 'distribucion/planilla_list.html'
    context_object_name = 'planillas'
    paginate_by = 10

    def get_queryset(self):
        qs = Planilla.objects.select_related('distribuidor')
        if estado := self.request.GET.get('estado'):
            qs = qs.filter(estado=estado)
        if fecha := self.request.GET.get('fecha'):
            qs = qs.filter(fecha=fecha)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['estados'] = Planilla.Estado.choices
        return ctx


class PlanillaDetailView(RolRequiredMixin, DetailView):
    roles_permitidos = SOLO_ADMIN
    model = Planilla
    template_name = 'distribucion/planilla_detail.html'
    context_object_name = 'planilla'

    def get_queryset(self):
        return Planilla.objects.prefetch_related(
            'entregas__cliente', 'entregas__producto',
            'averias__producto',
        ).select_related('distribuidor')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['total_ventas'] = sum(e.subtotal for e in self.object.entregas.all())
        return ctx


class PlanillaValidarView(RolRequiredMixin, View):
    roles_permitidos = SOLO_ADMIN
    def post(self, request, pk):
        planilla = get_object_or_404(Planilla, pk=pk)
        if planilla.estado == Planilla.Estado.PENDIENTE_VALIDACION:
            planilla.estado = Planilla.Estado.VALIDADA
            planilla.save(update_fields=['estado'])
            messages.success(request, f'Planilla del {planilla.fecha} validada.')
        return redirect('distribucion:planilla_detail', pk=pk)


# ── Vista de ruta (distribuidor) ──────────────────────────────────────────────

class PlanillaRutaListView(RolRequiredMixin, View):
    """Selector de planillas del día — permite crear múltiples por jornada."""
    roles_permitidos = ADMIN_DIST

    def get(self, request):
        hoy = date.today()
        planillas_hoy = Planilla.objects.filter(
            distribuidor=request.user, fecha=hoy
        ).prefetch_related('entregas').order_by('creado_en')
        return render(request, 'distribucion/planilla_ruta_list.html', {
            'planillas_hoy': planillas_hoy,
            'hoy': hoy,
        })

    def post(self, request):
        if request.POST.get('accion') == 'crear_planilla':
            if anio_cerrado(date.today().year):
                messages.error(
                    request,
                    f'El año {date.today().year} ya está cerrado; no se pueden crear planillas nuevas.',
                )
                return redirect('distribucion:ruta')
            planilla = Planilla.objects.create(
                distribuidor=request.user,
                fecha=date.today(),
                estado=Planilla.Estado.ABIERTA,
            )
            messages.success(request, 'Planilla creada.')
            return redirect('distribucion:ruta_planilla', pk=planilla.pk)
        return redirect('distribucion:ruta')


class PlanillaRutaView(RolRequiredMixin, View):
    """Vista de trabajo de una planilla específica."""
    roles_permitidos = ADMIN_DIST

    def _get_planilla(self, request, pk):
        return get_object_or_404(Planilla, pk=pk, distribuidor=request.user)

    def _context(self, request, planilla):
        clientes = Cliente.objects.filter(activo=True)
        productos = Producto.objects.filter(activo=True)

        cat_precios = {}
        for p in PrecioPorCategoria.objects.select_related('producto'):
            cat_precios.setdefault(p.categoria, {})[p.producto_id] = float(p.precio)
        precios = {c.id: cat_precios.get(c.categoria, {}) for c in clientes}

        entregas = planilla.entregas.select_related('cliente', 'producto').all()
        averias  = planilla.averias.select_related('producto').all()

        return {
            'planilla': planilla,
            'clientes': clientes,
            'productos': productos,
            'entregas': entregas,
            'averias': averias,
            'precios_json': json.dumps(precios),
            'hoy': date.today(),
            'modalidades': Entrega.ModalidadPago.choices,
            'total_ventas': sum(e.subtotal for e in entregas),
            'entrega_form': EntregaForm(),
            'averia_form': AveriaForm(),
        }

    def get(self, request, pk):
        planilla = self._get_planilla(request, pk)
        return render(request, 'distribucion/planilla_ruta.html', self._context(request, planilla))

    def post(self, request, pk):
        planilla = self._get_planilla(request, pk)
        accion = request.POST.get('accion')

        if accion in ('agregar_entrega', 'agregar_averia') and planilla.estado != Planilla.Estado.ABIERTA:
            messages.error(request, 'Esta planilla ya no está abierta; no se pueden agregar entregas ni averías.')
            return redirect('distribucion:ruta_planilla', pk=pk)

        if accion in ('agregar_entrega', 'agregar_averia') and anio_cerrado(planilla.fecha.year):
            messages.error(
                request,
                f'El año {planilla.fecha.year} ya está cerrado; no se pueden agregar '
                f'entregas ni averías a esta planilla.',
            )
            return redirect('distribucion:ruta_planilla', pk=pk)

        if accion == 'agregar_entrega':
            form = EntregaForm(request.POST)
            if form.is_valid():
                entrega = form.save(commit=False)
                entrega.planilla = planilla
                entrega.save()
                if entrega.modalidad_pago == Entrega.ModalidadPago.CREDITO and entrega.subtotal > 0:
                    monto = entrega.subtotal
                    Credito.objects.create(
                        cliente=entrega.cliente,
                        entrega=entrega,
                        monto=monto,
                        saldo_pendiente=monto,
                    )
                messages.success(request, 'Entrega registrada.')
            else:
                messages.error(request, 'Error en el formulario de entrega.')

        elif accion == 'agregar_averia':
            form = AveriaForm(request.POST)
            if form.is_valid():
                averia = form.save(commit=False)
                averia.planilla = planilla
                averia.save()
                messages.success(request, 'Avería registrada.')

        elif accion == 'enviar_validacion':
            if planilla.estado == Planilla.Estado.ABIERTA:
                planilla.estado = Planilla.Estado.PENDIENTE_VALIDACION
                planilla.save(update_fields=['estado'])
                messages.success(request, 'Planilla enviada para validación.')

        return redirect('distribucion:ruta_planilla', pk=pk)
