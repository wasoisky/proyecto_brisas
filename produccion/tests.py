from decimal import Decimal

from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from usuarios.models import Usuario

from .models import CompraInsumo, ConsumoInsumo, Insumo, Producto, Produccion, RecetaProducto, Regalia


class ProduccionTestMixin:
    """Helpers compartidos por los TestCase del módulo."""

    def crear_admin(self, username='maximino', password='brisas2024'):
        return Usuario.objects.create_user(
            username=username, password=password, rol='ADMIN',
        )

    def crear_producto(self, nombre='Botellón 20L', presentacion='BOT'):
        return Producto.objects.create(
            nombre=nombre, presentacion=presentacion, unidad_medida='unidad',
        )

    def crear_insumo(self, nombre='Tapa plástica', stock_actual=Decimal('50'),
                      stock_minimo=Decimal('10')):
        return Insumo.objects.create(
            nombre=nombre, categoria='TAP', unidad_medida='unidad',
            stock_actual=stock_actual, stock_minimo=stock_minimo,
        )


class VerificacionStockProduccionTests(ProduccionTestMixin, TestCase):
    """ProduccionCreateView debe bloquear el guardado si algún insumo no
    alcanza stock, y descontarlo atómicamente cuando sí alcanza."""

    def setUp(self):
        self.admin = self.crear_admin()
        self.client.force_login(self.admin)
        self.producto = self.crear_producto()
        self.insumo = self.crear_insumo(stock_actual=Decimal('50'))

    def _post_produccion(self, cantidad_consumo):
        data = {
            'fecha': '2026-08-30',
            'lote': 'PROD-20260830-001',
            'producto': self.producto.pk,
            'cantidad_producida': 10,
            'observaciones': '',
            'consumos-TOTAL_FORMS': '2',
            'consumos-INITIAL_FORMS': '0',
            'consumos-MIN_NUM_FORMS': '0',
            'consumos-MAX_NUM_FORMS': '1000',
            'consumos-0-insumo': self.insumo.pk,
            'consumos-0-cantidad': str(cantidad_consumo),
            'consumos-1-insumo': '',
            'consumos-1-cantidad': '',
        }
        return self.client.post(reverse('produccion:produccion_create'), data=data)

    def test_stock_insuficiente_bloquea_guardado_y_no_descuenta(self):
        response = self._post_produccion(cantidad_consumo='999')

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Produccion.objects.exists())
        self.insumo.refresh_from_db()
        self.assertEqual(self.insumo.stock_actual, Decimal('50'))

    def test_stock_suficiente_guarda_produccion_y_descuenta_stock(self):
        response = self._post_produccion(cantidad_consumo='20')

        self.assertRedirects(response, reverse('produccion:produccion_list'))
        self.assertTrue(Produccion.objects.filter(lote='PROD-20260830-001').exists())
        self.insumo.refresh_from_db()
        self.assertEqual(self.insumo.stock_actual, Decimal('30'))

    def test_stock_exacto_al_limite_es_aceptado(self):
        response = self._post_produccion(cantidad_consumo='50')

        self.assertRedirects(response, reverse('produccion:produccion_list'))
        self.insumo.refresh_from_db()
        self.assertEqual(self.insumo.stock_actual, Decimal('0'))


class CompraInsumoStockTests(ProduccionTestMixin, TestCase):
    def setUp(self):
        self.admin = self.crear_admin()
        self.client.force_login(self.admin)
        self.insumo = self.crear_insumo(stock_actual=Decimal('10'))

    def test_registrar_compra_incrementa_stock(self):
        response = self.client.post(reverse('produccion:compra_create'), data={
            'fecha': '2026-08-30',
            'insumo': self.insumo.pk,
            'cantidad': '25.00',
            'precio_unitario': '500.00',
            'proveedor': 'Proveedor Test',
            'factura': 'F-001',
        })

        self.assertRedirects(response, reverse('produccion:compra_list'))
        self.insumo.refresh_from_db()
        self.assertEqual(self.insumo.stock_actual, Decimal('35.00'))


class KardexInsumoTests(ProduccionTestMixin, TestCase):
    """El kardex debe combinar entradas (compras) y salidas (consumos) en
    orden cronológico y calcular el saldo acumulado correctamente."""

    def setUp(self):
        self.admin = self.crear_admin()
        self.client.force_login(self.admin)
        self.producto = self.crear_producto()
        self.insumo = self.crear_insumo(stock_actual=Decimal('0'))

    def test_saldo_acumulado_combina_entradas_y_salidas_en_orden_cronologico(self):
        CompraInsumo.objects.create(
            fecha='2026-08-01', insumo=self.insumo, cantidad=Decimal('100'),
            precio_unitario=Decimal('500'), registrado_por=self.admin,
        )
        produccion = Produccion.objects.create(
            fecha='2026-08-05', lote='PROD-A', producto=self.producto,
            cantidad_producida=10, registrado_por=self.admin,
        )
        ConsumoInsumo.objects.create(produccion=produccion, insumo=self.insumo, cantidad=Decimal('30'))
        CompraInsumo.objects.create(
            fecha='2026-08-10', insumo=self.insumo, cantidad=Decimal('20'),
            precio_unitario=Decimal('500'), registrado_por=self.admin,
        )

        response = self.client.get(reverse('produccion:insumo_kardex', args=[self.insumo.pk]))

        self.assertEqual(response.status_code, 200)
        saldos = [m['saldo'] for m in response.context['movimientos']]
        self.assertEqual(saldos, [100.0, 70.0, 90.0])
        self.assertEqual(response.context['saldo_calculado'], 90.0)

    def test_sin_movimientos_el_saldo_es_cero(self):
        response = self.client.get(reverse('produccion:insumo_kardex', args=[self.insumo.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['movimientos'], [])
        self.assertEqual(response.context['saldo_calculado'], 0)


class RecetaProductoTests(ProduccionTestMixin, TestCase):
    def setUp(self):
        self.admin = self.crear_admin()
        self.client.force_login(self.admin)
        self.producto = self.crear_producto()
        self.insumo = self.crear_insumo()

    def test_no_permite_dos_recetas_para_el_mismo_insumo_y_producto(self):
        RecetaProducto.objects.create(
            producto=self.producto, insumo=self.insumo, cantidad_por_unidad=Decimal('0.5'),
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                RecetaProducto.objects.create(
                    producto=self.producto, insumo=self.insumo, cantidad_por_unidad=Decimal('1'),
                )

    def test_receta_api_devuelve_los_insumos_del_producto(self):
        RecetaProducto.objects.create(
            producto=self.producto, insumo=self.insumo, cantidad_por_unidad=Decimal('0.75'),
        )

        response = self.client.get(reverse('produccion:receta_api', args=[self.producto.pk]))

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data['receta']), 1)
        linea = data['receta'][0]
        self.assertEqual(linea['insumo_id'], self.insumo.pk)
        self.assertEqual(linea['insumo_nombre'], self.insumo.nombre)
        self.assertEqual(Decimal(linea['cantidad_por_unidad']), Decimal('0.75'))

    def test_receta_api_de_producto_sin_receta_devuelve_lista_vacia(self):
        response = self.client.get(reverse('produccion:receta_api', args=[self.producto.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'receta': []})


class RegaliaTests(ProduccionTestMixin, TestCase):
    """Producto terminado entregado sin cobro (obsequio/cortesía/promoción)."""

    def setUp(self):
        self.admin = self.crear_admin()
        self.client.force_login(self.admin)
        self.producto = self.crear_producto()

    def test_registrar_regalia_sin_lote_de_origen(self):
        response = self.client.post(reverse('produccion:regalia_create'), data={
            'fecha': '2026-08-30',
            'producto': self.producto.pk,
            'produccion': '',
            'cantidad': '5',
            'destinatario': 'Escuela Boquerón',
            'motivo': Regalia.Motivo.OBSEQUIO_CLIENTE,
            'observaciones': '',
        })

        self.assertRedirects(response, reverse('produccion:regalia_list'))
        regalia = Regalia.objects.get()
        self.assertEqual(regalia.cantidad, 5)
        self.assertEqual(regalia.producto, self.producto)
        self.assertIsNone(regalia.produccion)
        self.assertEqual(regalia.registrado_por, self.admin)

    def test_registrar_regalia_con_lote_de_origen(self):
        produccion = Produccion.objects.create(
            fecha='2026-08-20', lote='PROD-X', producto=self.producto,
            cantidad_producida=100, registrado_por=self.admin,
        )

        response = self.client.post(reverse('produccion:regalia_create'), data={
            'fecha': '2026-08-30',
            'producto': self.producto.pk,
            'produccion': produccion.pk,
            'cantidad': '3',
            'destinatario': '',
            'motivo': Regalia.Motivo.PROMOCION,
            'observaciones': 'Lanzamiento de producto',
        })

        self.assertRedirects(response, reverse('produccion:regalia_list'))
        regalia = Regalia.objects.get()
        self.assertEqual(regalia.produccion, produccion)

    def test_lista_filtra_por_producto_y_calcula_total(self):
        otro_producto = self.crear_producto(nombre='Bolsa 300ml', presentacion='B3C')
        Regalia.objects.create(
            fecha='2026-08-10', producto=self.producto, cantidad=4,
            motivo=Regalia.Motivo.OTRO, registrado_por=self.admin,
        )
        Regalia.objects.create(
            fecha='2026-08-11', producto=otro_producto, cantidad=10,
            motivo=Regalia.Motivo.OTRO, registrado_por=self.admin,
        )

        response = self.client.get(
            reverse('produccion:regalia_list'), {'producto': self.producto.pk}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context['regalias']), [
            Regalia.objects.get(producto=self.producto),
        ])
        self.assertEqual(response.context['total_general'], 4)
