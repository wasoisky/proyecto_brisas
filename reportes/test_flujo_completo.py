"""Flujo operativo de punta a punta, como lo usará la empresa:
compra -> producción -> kardex -> ruta (API) -> validación -> reportes -> crédito."""
from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from distribucion.models import Cliente, Credito, Entrega, Planilla, PrecioPorCategoria
from produccion.models import Insumo, Produccion, RecetaProducto
from produccion.tests import ProduccionTestMixin
from usuarios.models import Usuario


class FlujoCompletoTests(ProduccionTestMixin, TestCase):
    def setUp(self):
        self.admin = self.crear_admin()
        self.client.force_login(self.admin)
        self.producto = self.crear_producto()
        self.insumo = self.crear_insumo(stock_actual=Decimal('50'), stock_minimo=Decimal('5'))
        RecetaProducto.objects.create(
            producto=self.producto, insumo=self.insumo, cantidad_por_unidad=Decimal('1'),
        )
        self.dist = Usuario.objects.create_user(username='nico', password='brisas2024', rol='DIST')
        PrecioPorCategoria.objects.create(
            categoria=Cliente.Categoria.REGULAR, producto=self.producto, precio=Decimal('3000'),
        )
        self.cliente = Cliente.objects.create(
            nombre='Tienda', categoria=Cliente.Categoria.REGULAR, autoriza_datos=True,
        )

    def _produccion(self, filas, lote='L-1', cantidad=10):
        data = {
            'fecha': date.today().isoformat(), 'lote': lote, 'producto': self.producto.pk,
            'cantidad_producida': cantidad, 'observaciones': '',
            'consumos-TOTAL_FORMS': len(filas), 'consumos-INITIAL_FORMS': 0,
            'consumos-MIN_NUM_FORMS': 0, 'consumos-MAX_NUM_FORMS': 1000,
        }
        for i, (insumo, cant) in enumerate(filas):
            data[f'consumos-{i}-insumo'] = insumo.pk
            data[f'consumos-{i}-cantidad'] = cant
        return self.client.post(reverse('produccion:produccion_create'), data)

    def test_compra_y_produccion_actualizan_stock_y_el_kardex_cuadra(self):
        self.client.post(reverse('produccion:compra_create'), {
            'fecha': date.today().isoformat(), 'insumo': self.insumo.pk,
            'cantidad': '20', 'precio_unitario': '100', 'proveedor': 'X', 'factura': 'F1',
        })
        self.insumo.refresh_from_db()
        self.assertEqual(self.insumo.stock_actual, Decimal('70'))

        self._produccion([(self.insumo, '30')])
        self.insumo.refresh_from_db()
        self.assertEqual(self.insumo.stock_actual, Decimal('40'))

        r = self.client.get(reverse('produccion:insumo_kardex', args=[self.insumo.pk]))
        self.assertEqual(r.context['saldo_inicial'], 50.0)
        self.assertEqual(r.context['saldo_calculado'], 40.0)

    def test_mismo_insumo_repetido_en_dos_filas_no_puede_dejar_stock_negativo(self):
        # 40 + 40 = 80 > 50 de stock: cada fila por separado alcanza, la suma no.
        self._produccion([(self.insumo, '40'), (self.insumo, '40')], lote='L-DUP')
        self.insumo.refresh_from_db()
        self.assertGreaterEqual(self.insumo.stock_actual, 0)

    def test_ruta_validacion_reportes_y_pago_de_credito(self):
        api = APIClient()
        api.force_authenticate(self.dist)
        r = api.post(reverse('distribucion:api_planilla_activa'))
        planilla_id = r.data['id']
        r = api.post(reverse('distribucion:api_entrega_create'), {
            'planilla': planilla_id, 'cliente': self.cliente.pk, 'producto': self.producto.pk,
            'cantidad': 4, 'precio_unitario': '3000', 'modalidad_pago': 'CRE', 'devolucion': 1,
        })
        self.assertEqual(r.status_code, 201)
        credito = Credito.objects.get()
        self.assertEqual(credito.monto, Decimal('9000'))

        # el distribuidor envía a validación desde la vista web
        self.client.force_login(self.dist)
        self.client.post(reverse('distribucion:ruta_planilla', args=[planilla_id]),
                         {'accion': 'enviar_validacion'})
        self.assertEqual(Planilla.objects.get(pk=planilla_id).estado, Planilla.Estado.PENDIENTE_VALIDACION)

        # el admin valida
        self.client.force_login(self.admin)
        self.client.post(reverse('distribucion:planilla_validar', args=[planilla_id]))
        self.assertEqual(Planilla.objects.get(pk=planilla_id).estado, Planilla.Estado.VALIDADA)

        # reportes
        for name in ('reportes:dashboard', 'reportes:ventas', 'reportes:ventas_excel',
                     'reportes:ventas_pdf', 'reportes:creditos', 'reportes:anual'):
            resp = self.client.get(reverse(name))
            self.assertEqual(resp.status_code, 200, name)
        ctx = self.client.get(reverse('reportes:ventas')).context
        self.assertContains(self.client.get(reverse('reportes:ventas')), 'Botellón 20L')
        self.assertEqual(ctx['gran_total'], 9000.0)

        # pago parcial y total del crédito
        self.client.post(reverse('reportes:credito_pagar', args=[credito.pk]), {'monto_pago': '4000'})
        credito.refresh_from_db()
        self.assertEqual(credito.saldo_pendiente, Decimal('5000'))
        self.client.post(reverse('reportes:credito_pagar', args=[credito.pk]), {'monto_pago': '5000'})
        credito.refresh_from_db()
        self.assertTrue(credito.pagado)
