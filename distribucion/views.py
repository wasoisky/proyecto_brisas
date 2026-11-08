import json
from datetime import date
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.db import transaction
from usuarios.mixins import RolRequiredMixin, SOLO_ADMIN, ADMIN_DIST
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import ListView, CreateView, UpdateView, DetailView

from produccion.models import Producto
from reportes.cierres import anio_cerrado
from .forms import ClienteForm, PlanillaForm, EntregaForm, AveriaForm
from .conciliacion import disponible_en_planta, resumen_planilla
from .models import Cliente, PrecioPorCategoria, Planilla, Entrega, Averia, Credito, CargaRuta


def json_para_script(datos):
    """JSON seguro para incrustar dentro de un <script> (con |safe en la plantilla).

    json.dumps no escapa '<', '>' ni '&', así que un valor como «</script>» (p. ej. un
    nombre de producto) cerraría el bloque de JavaScript. Se escapan como \\uXXXX, que
    JSON.parse/JavaScript interpretan igual.
    """
    return (
        json.dumps(datos)
        .replace('<', '\\u003c')
        .replace('>', '\\u003e')
        .replace('&', '\\u0026')
    )


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

    def get_template_names(self):
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return ['distribucion/_cliente_tabla.html']
        return [self.template_name]


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


# ── Precios por categoría (admin) ─────────────────────────────────────────────

class PreciosView(RolRequiredMixin, View):
    """El ADMIN ajusta el precio de cada producto por categoría (REG/MAY).

    Cambiar un precio solo afecta entregas futuras: cada Entrega guarda su propio
    precio_unitario. Un campo vacío no toca el precio existente.
    """
    roles_permitidos = SOLO_ADMIN

    def _filas(self):
        existentes = {
            (p.producto_id, p.categoria): p.precio for p in PrecioPorCategoria.objects.all()
        }
        filas = []
        for prod in Producto.objects.filter(activo=True).order_by('nombre'):
            filas.append({
                'producto': prod,
                'reg': existentes.get((prod.pk, Cliente.Categoria.REGULAR)),
                'may': existentes.get((prod.pk, Cliente.Categoria.MAYORISTA)),
            })
        return filas

    def get(self, request):
        return render(request, 'distribucion/precios.html', {'filas': self._filas()})

    def post(self, request):
        cambios, errores = [], []
        for prod in Producto.objects.filter(activo=True):
            for cat, etiqueta in Cliente.Categoria.choices:
                crudo = (request.POST.get(f'precio_{prod.pk}_{cat}') or '').strip().replace(',', '.')
                if crudo == '':
                    continue
                try:
                    valor = Decimal(crudo)
                    if not valor.is_finite() or valor < 0 or valor >= Decimal('100000000'):
                        raise InvalidOperation
                except InvalidOperation:
                    errores.append(f'{prod.nombre} ({etiqueta}): precio inválido.')
                    continue
                cambios.append((prod, cat, valor.quantize(Decimal('0.01'))))

        if errores:
            messages.error(request, 'No se guardó nada. ' + ' '.join(errores))
            return redirect('distribucion:precios')

        with transaction.atomic():
            for prod, cat, valor in cambios:
                PrecioPorCategoria.objects.update_or_create(
                    producto=prod, categoria=cat, defaults={'precio': valor},
                )
        messages.success(request, f'Precios guardados ({len(cambios)} actualizados).')
        return redirect('distribucion:precios')


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
        ctx['conciliacion'] = resumen_planilla(self.object)
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
        resumen = resumen_planilla(planilla)

        return {
            'planilla': planilla,
            'clientes': clientes,
            'productos': productos,
            'entregas': entregas,
            'averias': averias,
            'precios_json': json_para_script(precios),
            'hoy': date.today(),
            'modalidades': Entrega.ModalidadPago.choices,
            'total_ventas': sum(e.subtotal for e in entregas),
            'entrega_form': EntregaForm(),
            'averia_form': AveriaForm(),
            'resumen': resumen,
            'camion_json': json_para_script({
                str(f['producto'].pk): {
                    'nombre': f['producto'].nombre, 'cargado': f['cargado'],
                    'entregado': f['entregado'], 'averiado': f['averiado'],
                } for f in resumen
            }),
            'disponibles_json': json_para_script({
                str(p.pk): disponible_en_planta(p) for p in productos
            }),
        }

    def _guardar_carga(self, request, planilla):
        """Registra (o reemplaza) lo que se carga de un producto en el camión."""
        producto = Producto.objects.filter(pk=request.POST.get('producto') or 0, activo=True).first()
        try:
            cantidad = int(request.POST.get('cantidad', ''))
        except (TypeError, ValueError):
            cantidad = 0
        if not producto or cantidad < 1:
            messages.error(request, 'Elige el producto y una cantidad de al menos 1.')
            return
        ya_salio = next(
            (f['entregado'] + f['averiado'] for f in resumen_planilla(planilla) if f['producto'] == producto), 0,
        )
        if cantidad < ya_salio:
            messages.error(
                request,
                f'{producto.nombre}: ya registraste {ya_salio} entre entregas y averías; '
                f'la carga no puede ser menor.',
            )
            return
        anterior = CargaRuta.objects.filter(planilla=planilla, producto=producto).first()
        disponible = disponible_en_planta(producto) + (anterior.cantidad_cargada if anterior else 0)
        CargaRuta.objects.update_or_create(
            planilla=planilla, producto=producto, defaults={'cantidad_cargada': cantidad},
        )
        messages.success(request, f'Carga guardada: {producto.nombre} x{cantidad}.')
        if cantidad > disponible:
            messages.warning(
                request,
                f'Ojo: en planta hay {max(disponible, 0)} de {producto.nombre} según la producción '
                f'registrada y estás cargando {cantidad}. Avisa si falta registrar producción.',
            )

    def _cerrar_ruta(self, request, planilla):
        """Valida y guarda la devolución por producto. Sin cargas, no exige nada."""
        cargas = list(planilla.cargas.select_related('producto'))
        devueltos = {}
        for c in cargas:
            crudo = request.POST.get(f'devuelto_{c.producto_id}')
            try:
                valor = int(crudo)
            except (TypeError, ValueError):
                messages.error(request, f'Falta la devolución de {c.producto.nombre} (escribe 0 si no devolviste nada).')
                return False
            if valor < 0 or valor > c.cantidad_cargada:
                messages.error(
                    request,
                    f'{c.producto.nombre}: la devolución debe estar entre 0 y lo que cargaste ({c.cantidad_cargada}).',
                )
                return False
            devueltos[c.pk] = valor
        for c in cargas:
            c.cantidad_devuelta = devueltos[c.pk]
            c.save(update_fields=['cantidad_devuelta'])
        return True

    def get(self, request, pk):
        planilla = self._get_planilla(request, pk)
        return render(request, 'distribucion/planilla_ruta.html', self._context(request, planilla))

    def post(self, request, pk):
        planilla = self._get_planilla(request, pk)
        accion = request.POST.get('accion')

        if accion in ('agregar_entrega', 'agregar_averia', 'guardar_carga') and planilla.estado != Planilla.Estado.ABIERTA:
            messages.error(request, 'Esta planilla ya no está abierta; no se pueden agregar entregas ni averías.')
            return redirect('distribucion:ruta_planilla', pk=pk)

        if accion in ('agregar_entrega', 'agregar_averia', 'guardar_carga') and anio_cerrado(planilla.fecha.year):
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

        elif accion == 'guardar_carga':
            self._guardar_carga(request, planilla)

        elif accion == 'enviar_validacion':
            if planilla.estado == Planilla.Estado.ABIERTA and self._cerrar_ruta(request, planilla):
                planilla.estado = Planilla.Estado.PENDIENTE_VALIDACION
                planilla.save(update_fields=['estado'])
                messages.success(request, 'Planilla enviada para validación.')

        return redirect('distribucion:ruta_planilla', pk=pk)
