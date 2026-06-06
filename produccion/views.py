from datetime import date

from django.contrib import messages
from usuarios.mixins import RolRequiredMixin, ADMIN_PROD
from django.db import transaction
from django.db.models import F
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import ListView, CreateView, UpdateView, DetailView
from django.shortcuts import get_object_or_404, redirect

from .models import Producto, Insumo, Produccion, CompraInsumo
from .forms import ProductoForm, InsumoForm, ProduccionForm, ConsumoInsumoFormSet, CompraInsumoForm


# ── Producto ──────────────────────────────────────────────────────────────────

class ProductoListView(RolRequiredMixin, ListView):
    roles_permitidos = ADMIN_PROD
    model = Producto
    template_name = 'produccion/producto_list.html'
    context_object_name = 'productos'

    def get_queryset(self):
        qs = Producto.objects.all()
        presentacion = self.request.GET.get('presentacion')
        activo = self.request.GET.get('activo')
        if presentacion:
            qs = qs.filter(presentacion=presentacion)
        if activo in ('1', '0'):
            qs = qs.filter(activo=activo == '1')
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['presentaciones'] = Producto.Presentacion.choices
        return ctx


class ProductoCreateView(RolRequiredMixin, CreateView):
    roles_permitidos = ADMIN_PROD
    model = Producto
    form_class = ProductoForm
    template_name = 'produccion/producto_form.html'
    success_url = reverse_lazy('produccion:producto_list')

    def form_valid(self, form):
        messages.success(self.request, 'Producto creado correctamente.')
        return super().form_valid(form)


class ProductoUpdateView(RolRequiredMixin, UpdateView):
    roles_permitidos = ADMIN_PROD
    model = Producto
    form_class = ProductoForm
    template_name = 'produccion/producto_form.html'
    success_url = reverse_lazy('produccion:producto_list')

    def form_valid(self, form):
        messages.success(self.request, 'Producto actualizado correctamente.')
        return super().form_valid(form)


class ProductoToggleActivoView(RolRequiredMixin, View):
    roles_permitidos = ADMIN_PROD
    def post(self, request, pk):
        producto = get_object_or_404(Producto, pk=pk)
        producto.activo = not producto.activo
        producto.save(update_fields=['activo'])
        estado = 'activado' if producto.activo else 'desactivado'
        messages.success(request, f'Producto "{producto.nombre}" {estado}.')
        return redirect('produccion:producto_list')


# ── Insumo ────────────────────────────────────────────────────────────────────

class InsumoListView(RolRequiredMixin, ListView):
    roles_permitidos = ADMIN_PROD
    model = Insumo
    template_name = 'produccion/insumo_list.html'
    context_object_name = 'insumos'

    def get_queryset(self):
        qs = Insumo.objects.all()
        categoria = self.request.GET.get('categoria')
        activo = self.request.GET.get('activo')
        solo_alertas = self.request.GET.get('alertas')
        if categoria:
            qs = qs.filter(categoria=categoria)
        if activo in ('1', '0'):
            qs = qs.filter(activo=activo == '1')
        if solo_alertas == '1':
            # stock_actual <= stock_minimo
            from django.db.models import F
            qs = qs.filter(stock_actual__lte=F('stock_minimo'))
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['categorias'] = Insumo.Categoria.choices
        from django.db.models import F
        ctx['total_alertas'] = Insumo.objects.filter(
            activo=True, stock_actual__lte=F('stock_minimo')
        ).count()
        return ctx


class InsumoCreateView(RolRequiredMixin, CreateView):
    roles_permitidos = ADMIN_PROD
    model = Insumo
    form_class = InsumoForm
    template_name = 'produccion/insumo_form.html'
    success_url = reverse_lazy('produccion:insumo_list')

    def form_valid(self, form):
        messages.success(self.request, 'Insumo registrado correctamente.')
        return super().form_valid(form)


class InsumoUpdateView(RolRequiredMixin, UpdateView):
    roles_permitidos = ADMIN_PROD
    model = Insumo
    form_class = InsumoForm
    template_name = 'produccion/insumo_form.html'
    success_url = reverse_lazy('produccion:insumo_list')

    def form_valid(self, form):
        messages.success(self.request, 'Insumo actualizado correctamente.')
        return super().form_valid(form)


class InsumoToggleActivoView(RolRequiredMixin, View):
    roles_permitidos = ADMIN_PROD
    def post(self, request, pk):
        insumo = get_object_or_404(Insumo, pk=pk)
        insumo.activo = not insumo.activo
        insumo.save(update_fields=['activo'])
        estado = 'activado' if insumo.activo else 'desactivado'
        messages.success(request, f'Insumo "{insumo.nombre}" {estado}.')
        return redirect('produccion:insumo_list')


# ── Produccion ────────────────────────────────────────────────────────────────

class ProduccionListView(RolRequiredMixin, ListView):
    roles_permitidos = ADMIN_PROD
    model = Produccion
    template_name = 'produccion/produccion_list.html'
    context_object_name = 'registros'

    def get_queryset(self):
        qs = Produccion.objects.select_related('producto', 'registrado_por')
        if fecha := self.request.GET.get('fecha'):
            qs = qs.filter(fecha=fecha)
        if producto := self.request.GET.get('producto'):
            qs = qs.filter(producto_id=producto)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['productos'] = Producto.objects.filter(activo=True)
        return ctx


class ProduccionCreateView(RolRequiredMixin, CreateView):
    roles_permitidos = ADMIN_PROD
    model = Produccion
    form_class = ProduccionForm
    template_name = 'produccion/produccion_form.html'

    def get_initial(self):
        hoy = date.today()
        count = Produccion.objects.filter(fecha=hoy).count() + 1
        return {
            'fecha': hoy,
            'lote': f'PROD-{hoy.strftime("%Y%m%d")}-{count:03d}',
        }

    def get(self, request, *args, **kwargs):
        self.object = None
        return self.render_to_response(self.get_context_data(
            form=self.get_form(),
            formset=ConsumoInsumoFormSet(prefix='consumos'),
        ))

    def post(self, request, *args, **kwargs):
        self.object = None
        form = self.get_form()
        formset = ConsumoInsumoFormSet(request.POST, prefix='consumos')
        if form.is_valid() and formset.is_valid():
            return self._guardar(form, formset)
        return self.render_to_response(self.get_context_data(form=form, formset=formset))

    def _guardar(self, form, formset):
        consumos_validos = [
            f for f in formset
            if f.cleaned_data and not f.cleaned_data.get('DELETE')
        ]
        # Verificar stock antes de guardar
        for f in consumos_validos:
            insumo = f.cleaned_data['insumo']
            cantidad = f.cleaned_data['cantidad']
            if insumo.stock_actual < cantidad:
                messages.error(
                    self.request,
                    f'Stock insuficiente: {insumo.nombre} — '
                    f'disponible {insumo.stock_actual} {insumo.unidad_medida}, requerido {cantidad}.',
                )
                return self.render_to_response(
                    self.get_context_data(form=form, formset=formset)
                )

        with transaction.atomic():
            self.object = form.save(commit=False)
            self.object.registrado_por = self.request.user
            self.object.save()
            formset.instance = self.object
            formset.save()
            for f in consumos_validos:
                Insumo.objects.filter(pk=f.cleaned_data['insumo'].pk).update(
                    stock_actual=F('stock_actual') - f.cleaned_data['cantidad']
                )

        messages.success(self.request, f'Lote {self.object.lote} registrado correctamente.')
        return redirect('produccion:produccion_list')


class ProduccionDetailView(RolRequiredMixin, DetailView):
    roles_permitidos = ADMIN_PROD
    model = Produccion
    template_name = 'produccion/produccion_detail.html'
    context_object_name = 'registro'

    def get_queryset(self):
        return Produccion.objects.prefetch_related('consumos__insumo').select_related(
            'producto', 'registrado_por'
        )


# ── CompraInsumo ──────────────────────────────────────────────────────────────

class CompraInsumoListView(RolRequiredMixin, ListView):
    roles_permitidos = ADMIN_PROD
    model = CompraInsumo
    template_name = 'produccion/compra_list.html'
    context_object_name = 'compras'

    def get_queryset(self):
        qs = CompraInsumo.objects.select_related('insumo', 'registrado_por')
        if insumo_id := self.request.GET.get('insumo'):
            qs = qs.filter(insumo_id=insumo_id)
        if desde := self.request.GET.get('desde'):
            qs = qs.filter(fecha__gte=desde)
        if hasta := self.request.GET.get('hasta'):
            qs = qs.filter(fecha__lte=hasta)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['insumos'] = Insumo.objects.filter(activo=True)
        compras = ctx['compras']
        ctx['total_general'] = sum(c.total for c in compras)
        return ctx


class CompraInsumoCreateView(RolRequiredMixin, CreateView):
    roles_permitidos = ADMIN_PROD
    model = CompraInsumo
    form_class = CompraInsumoForm
    template_name = 'produccion/compra_form.html'
    success_url = reverse_lazy('produccion:compra_list')

    def get_initial(self):
        return {'fecha': date.today()}

    def form_valid(self, form):
        with transaction.atomic():
            compra = form.save(commit=False)
            compra.registrado_por = self.request.user
            compra.save()
            Insumo.objects.filter(pk=compra.insumo_id).update(
                stock_actual=F('stock_actual') + compra.cantidad
            )
        messages.success(
            self.request,
            f'Compra registrada: {compra.cantidad} {compra.insumo.unidad_medida} '
            f'de {compra.insumo.nombre}. Stock actualizado.',
        )
        return redirect(self.success_url)