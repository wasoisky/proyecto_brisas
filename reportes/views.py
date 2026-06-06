from datetime import date, timedelta
from io import BytesIO

from django.contrib import messages
from usuarios.mixins import RolRequiredMixin, SOLO_ADMIN
from django.db.models import Sum, Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views import View
from django.views.generic import ListView, CreateView, TemplateView

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment

from distribucion.models import Planilla, Entrega, Credito
from produccion.models import Produccion, Insumo
from usuarios.models import Usuario
from .forms import DescuadreForm, FiltroVentasForm
from .models import Descuadre


# ── Dashboard ─────────────────────────────────────────────────────────────────

class ReportesDashboardView(RolRequiredMixin, TemplateView):
    roles_permitidos = SOLO_ADMIN
    template_name = 'reportes/dashboard.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        hoy = date.today()
        inicio_mes = hoy.replace(day=1)

        ctx['total_produccion_mes'] = (
            Produccion.objects
            .filter(fecha__gte=inicio_mes)
            .aggregate(total=Sum('cantidad_producida'))['total'] or 0
        )
        ctx['total_ventas_mes'] = sum(
            e.subtotal for e in
            Entrega.objects.filter(planilla__fecha__gte=inicio_mes).select_related('producto')
        )
        ctx['creditos_pendientes'] = (
            Credito.objects.filter(pagado=False)
            .aggregate(total=Sum('saldo_pendiente'))['total'] or 0
        )
        ctx['alertas_insumos'] = (
            Insumo.objects.filter(
                activo=True, stock_actual__lte=0
            ).count()
        )
        ctx['descuadres_activos'] = Descuadre.objects.filter(resuelto=False).count()
        ctx['planillas_pendientes'] = Planilla.objects.filter(
            estado=Planilla.Estado.PENDIENTE_VALIDACION
        ).count()
        ctx['hoy'] = str(hoy)            # ISO string para URLs
        ctx['inicio_mes'] = str(inicio_mes)  # primer día del mes
        return ctx


# ── Ventas consolidadas ───────────────────────────────────────────────────────

class VentasConsolidadasView(RolRequiredMixin, TemplateView):
    roles_permitidos = SOLO_ADMIN
    template_name = 'reportes/ventas.html'

    def _get_filtros(self):
        hoy = date.today()
        distribuidores = Usuario.objects.filter(rol='DIST')
        form = FiltroVentasForm(
            distribuidores,
            self.request.GET or {'fecha_desde': hoy.replace(day=1), 'fecha_hasta': hoy},
        )
        fecha_desde = None
        fecha_hasta = None
        distribuidor_id = None
        if form.is_valid():
            fecha_desde = form.cleaned_data.get('fecha_desde') or hoy.replace(day=1)
            fecha_hasta = form.cleaned_data.get('fecha_hasta') or hoy
            distribuidor_id = form.cleaned_data.get('distribuidor') or None
        return form, fecha_desde, fecha_hasta, distribuidor_id

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        form, f_desde, f_hasta, dist_id = self._get_filtros()
        ctx['form'] = form

        qs = Entrega.objects.filter(
            planilla__fecha__gte=f_desde,
            planilla__fecha__lte=f_hasta,
        ).select_related('producto', 'cliente', 'planilla__distribuidor')

        if dist_id:
            qs = qs.filter(planilla__distribuidor_id=dist_id)

        # Ventas por producto
        por_producto = {}
        for e in qs:
            key = e.producto.nombre
            if key not in por_producto:
                por_producto[key] = {'cantidad': 0, 'total': 0}
            por_producto[key]['cantidad'] += e.cantidad - e.devolucion
            por_producto[key]['total'] += float(e.subtotal)

        # Ventas por distribuidor
        por_dist = {}
        for e in qs:
            nombre = e.planilla.distribuidor.get_full_name() or e.planilla.distribuidor.username
            if nombre not in por_dist:
                por_dist[nombre] = {'entregas': 0, 'total': 0}
            por_dist[nombre]['entregas'] += 1
            por_dist[nombre]['total'] += float(e.subtotal)

        # Desglose por modalidad de pago
        pago_totales = {'EFE': 0, 'NEQ': 0, 'CRE': 0}
        for e in qs:
            pago_totales[e.modalidad_pago] = pago_totales.get(e.modalidad_pago, 0) + float(e.subtotal)

        ctx['por_producto'] = sorted(por_producto.items(), key=lambda x: -x[1]['total'])
        ctx['por_dist'] = sorted(por_dist.items(), key=lambda x: -x[1]['total'])
        ctx['pago_totales'] = pago_totales
        ctx['gran_total'] = sum(v['total'] for v in por_producto.values())
        ctx['fecha_desde'] = str(f_desde)   # ISO YYYY-MM-DD para URLs y date inputs
        ctx['fecha_hasta'] = str(f_hasta)
        return ctx


class ExportarVentasExcelView(RolRequiredMixin, View):
    roles_permitidos = SOLO_ADMIN
    def get(self, request):
        hoy = date.today()
        f_desde = request.GET.get('fecha_desde') or str(hoy.replace(day=1))
        f_hasta = request.GET.get('fecha_hasta') or str(hoy)

        qs = Entrega.objects.filter(
            planilla__fecha__gte=f_desde,
            planilla__fecha__lte=f_hasta,
        ).select_related('producto', 'cliente', 'planilla__distribuidor').order_by('planilla__fecha')

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = 'Ventas'

        header_font = Font(bold=True, color='FFFFFF')
        header_fill = PatternFill('solid', fgColor='1F4E79')
        headers = ['Fecha', 'Distribuidor', 'Cliente', 'Producto',
                   'Cantidad', 'Devolución', 'Precio unit.', 'Subtotal', 'Pago']
        for col, h in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=h)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal='center')

        for row, e in enumerate(qs, 2):
            ws.append([
                e.planilla.fecha,
                e.planilla.distribuidor.get_full_name() or e.planilla.distribuidor.username,
                e.cliente.nombre,
                e.producto.nombre,
                e.cantidad,
                e.devolucion,
                float(e.precio_unitario),
                float(e.subtotal),
                e.get_modalidad_pago_display(),
            ])

        for col in ws.columns:
            ws.column_dimensions[col[0].column_letter].width = max(len(str(c.value or '')) for c in col) + 4

        buf = BytesIO()
        wb.save(buf)
        buf.seek(0)
        nombre = f'ventas_{f_desde}_{f_hasta}.xlsx'
        resp = HttpResponse(buf, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        resp['Content-Disposition'] = f'attachment; filename="{nombre}"'
        return resp


# ── Descuadres ────────────────────────────────────────────────────────────────

class DescuadreListView(RolRequiredMixin, ListView):
    roles_permitidos = SOLO_ADMIN
    model = Descuadre
    template_name = 'reportes/descuadres.html'
    context_object_name = 'descuadres'

    def get_queryset(self):
        qs = Descuadre.objects.select_related('detectado_por')
        if tipo := self.request.GET.get('tipo'):
            qs = qs.filter(tipo=tipo)
        resuelto = self.request.GET.get('resuelto')
        if resuelto in ('1', '0'):
            qs = qs.filter(resuelto=resuelto == '1')
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['tipos'] = Descuadre.TipoDescuadre.choices
        ctx['form'] = DescuadreForm()
        return ctx


class DescuadreCreateView(RolRequiredMixin, CreateView):
    roles_permitidos = SOLO_ADMIN
    model = Descuadre
    form_class = DescuadreForm
    template_name = 'reportes/descuadres.html'

    def form_valid(self, form):
        form.instance.detectado_por = self.request.user
        descuadre = form.save()
        messages.success(self.request, f'Descuadre registrado: {descuadre}')
        return redirect('reportes:descuadres')

    def form_invalid(self, form):
        messages.error(self.request, 'Error al registrar el descuadre.')
        return redirect('reportes:descuadres')


class DescuadreResolverView(RolRequiredMixin, View):
    roles_permitidos = SOLO_ADMIN
    def post(self, request, pk):
        descuadre = get_object_or_404(Descuadre, pk=pk)
        if not descuadre.resuelto:
            descuadre.resuelto = True
            descuadre.resuelto_en = timezone.now()
            descuadre.save(update_fields=['resuelto', 'resuelto_en'])
            messages.success(request, 'Descuadre marcado como resuelto.')
        return redirect('reportes:descuadres')


# ── Créditos pendientes ───────────────────────────────────────────────────────

class CreditosPendientesView(RolRequiredMixin, ListView):
    roles_permitidos = SOLO_ADMIN
    template_name = 'reportes/creditos.html'
    context_object_name = 'creditos'

    def get_queryset(self):
        qs = Credito.objects.filter(pagado=False).select_related(
            'cliente', 'entrega__planilla__distribuidor', 'entrega__producto'
        )
        if cliente := self.request.GET.get('cliente'):
            qs = qs.filter(cliente__nombre__icontains=cliente)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['total_pendiente'] = (
            Credito.objects.filter(pagado=False)
            .aggregate(t=Sum('saldo_pendiente'))['t'] or 0
        )
        return ctx


class CreditoPagarView(RolRequiredMixin, View):
    roles_permitidos = SOLO_ADMIN

    def post(self, request, pk):
        credito = get_object_or_404(Credito, pk=pk, pagado=False)
        try:
            monto_pago = round(float(request.POST.get('monto_pago', 0)), 2)
        except (ValueError, TypeError):
            monto_pago = 0

        if monto_pago <= 0:
            messages.error(request, 'El monto del pago debe ser mayor a cero.')
            return redirect('reportes:creditos')

        if monto_pago > float(credito.saldo_pendiente):
            messages.error(
                request,
                f'El monto ingresado (${monto_pago}) supera el saldo pendiente '
                f'(${credito.saldo_pendiente}).',
            )
            return redirect('reportes:creditos')

        credito.saldo_pendiente = round(float(credito.saldo_pendiente) - monto_pago, 2)
        if credito.saldo_pendiente <= 0:
            credito.saldo_pendiente = 0
            credito.pagado = True
            credito.fecha_pago = date.today()
            messages.success(
                request,
                f'Crédito de {credito.cliente.nombre} pagado completamente.',
            )
        else:
            messages.success(
                request,
                f'Abono de ${monto_pago} registrado. Saldo restante: ${credito.saldo_pendiente}.',
            )
        credito.save(update_fields=['saldo_pendiente', 'pagado', 'fecha_pago'])
        return redirect('reportes:creditos')
