"""Regla de negocio: los reportes del ADMIN solo cuentan lo que ya fue validado.

Una planilla ABIERTA o PENDIENTE DE VALIDACIÓN aún no está auditada, así que sus
ventas y créditos no entran en ningún total; al validarla sí entran.
"""
from datetime import date
from decimal import Decimal
from io import BytesIO

import openpyxl
from django.test import TestCase
from django.urls import reverse

from distribucion.models import Cliente, Credito, Entrega, Planilla, PrecioPorCategoria
from produccion.models import Producto
from usuarios.models import Usuario


class SoloValidadasTests(TestCase):
    def setUp(self):
        self.admin = Usuario.objects.create_user(username='edwin', password='x', rol='ADMIN')
        self.dist = Usuario.objects.create_user(username='nico', password='x', rol='DIST')
        self.producto = Producto.objects.create(nombre='Botellón', presentacion='BOT')
        PrecioPorCategoria.objects.create(categoria='REG', producto=self.producto, precio=Decimal('1000'))
        self.c_val = Cliente.objects.create(nombre='ClienteValidado', categoria='REG')
        self.c_pen = Cliente.objects.create(nombre='ClientePendiente', categoria='REG')
        self.c_abr = Cliente.objects.create(nombre='ClienteAbierto', categoria='REG')
        hoy = date.today()
        # Tres planillas el mismo día (están permitidas varias por jornada)
        self.p_val = Planilla.objects.create(distribuidor=self.dist, fecha=hoy, estado=Planilla.Estado.VALIDADA)
        self.p_pen = Planilla.objects.create(distribuidor=self.dist, fecha=hoy, estado=Planilla.Estado.PENDIENTE_VALIDACION)
        self.p_abr = Planilla.objects.create(distribuidor=self.dist, fecha=hoy, estado=Planilla.Estado.ABIERTA)
        self.e_val = self._entrega(self.p_val, self.c_val, 10)      # 10.000 validado
        self.e_pen = self._entrega(self.p_pen, self.c_pen, 20)      # 20.000 pendiente
        self.e_abr = self._entrega(self.p_abr, self.c_abr, 30)      # 30.000 abierta
        self.client.force_login(self.admin)

    def _entrega(self, planilla, cliente, cantidad):
        e = Entrega.objects.create(
            planilla=planilla, cliente=cliente, producto=self.producto, cantidad=cantidad,
            precio_unitario=Decimal('1000'), modalidad_pago='CRE',
        )
        Credito.objects.create(cliente=cliente, entrega=e, monto=e.subtotal, saldo_pendiente=e.subtotal)
        return e

    def test_dashboard_solo_cuenta_ventas_y_creditos_validados(self):
        ctx = self.client.get(reverse('reportes:dashboard')).context
        self.assertEqual(ctx['total_ventas_mes'], 10000)
        self.assertEqual(ctx['creditos_pendientes'], 10000)

    def test_dashboard_informa_aparte_lo_que_esta_por_validar(self):
        ctx = self.client.get(reverse('reportes:dashboard')).context
        self.assertEqual(ctx['ventas_por_validar'], 50000)
        self.assertEqual(ctx['planillas_pendientes'], 1)  # el contador existente no cambia

    def test_validar_una_planilla_hace_que_sus_ventas_entren_al_reporte(self):
        self.client.post(reverse('distribucion:planilla_validar', args=[self.p_pen.pk]))
        ctx = self.client.get(reverse('reportes:dashboard')).context
        self.assertEqual(ctx['total_ventas_mes'], 30000)
        self.assertEqual(ctx['creditos_pendientes'], 30000)
        self.assertEqual(ctx['ventas_por_validar'], 30000)  # queda la abierta

    def test_ventas_consolidadas_solo_validadas(self):
        ctx = self.client.get(reverse('reportes:ventas')).context
        self.assertEqual(ctx['gran_total'], 10000)

    def test_excel_de_ventas_solo_incluye_planillas_validadas(self):
        resp = self.client.get(reverse('reportes:ventas_excel'))
        self.assertEqual(resp.status_code, 200)
        wb = openpyxl.load_workbook(BytesIO(resp.content))
        texto = ' '.join(str(c.value) for ws in wb for fila in ws.iter_rows() for c in fila if c.value is not None)
        self.assertIn('ClienteValidado', texto)
        self.assertNotIn('ClientePendiente', texto)
        self.assertNotIn('ClienteAbierto', texto)

    def test_pdf_de_ventas_responde(self):
        self.assertEqual(self.client.get(reverse('reportes:ventas_pdf')).status_code, 200)

    def test_listado_de_creditos_solo_muestra_los_de_planillas_validadas(self):
        ctx = self.client.get(reverse('reportes:creditos')).context
        self.assertEqual([c.cliente.nombre for c in ctx['creditos']], ['ClienteValidado'])
        self.assertEqual(ctx['total_pendiente'], 10000)

    def test_no_se_puede_pagar_un_credito_de_planilla_sin_validar(self):
        credito = Credito.objects.get(entrega=self.e_pen)
        self.client.post(reverse('reportes:credito_pagar', args=[credito.pk]), {'monto_pago': '5000'})
        credito.refresh_from_db()
        self.assertEqual(credito.saldo_pendiente, Decimal('20000'))

    def test_reporte_anual_solo_cuenta_lo_validado(self):
        ctx = self.client.get(reverse('reportes:anual')).context
        self.assertEqual(ctx['total_ventas'], 10000)
        self.assertEqual(ctx['creditos_generados'], 10000)
        self.assertEqual(ctx['creditos_pendientes'], 10000)
