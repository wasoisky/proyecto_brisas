from decimal import Decimal

from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from usuarios.models import Usuario

from .models import (
    CompraInsumo, ConsumoInsumo, Insumo, Producto, Produccion, RecetaProducto, Regalia,
    CategoriaInsumo, UnidadMedida,
)


class ProduccionTestMixin:
    """Helpers compartidos por los TestCase del módulo.

    CategoriaInsumo y UnidadMedida ya vienen poblados por la migración de
    datos 0006_poblar_catalogos (9 categorías, 13 unidades) — los tests solo
    los leen, no los crean.
    """

    def crear_admin(self, username='maximino', password='brisas2024'):
        return Usuario.objects.create_user(
            username=username, password=password, rol='ADMIN',
        )

    def unidad(self, nombre='unidad'):
        return UnidadMedida.objects.get(nombre=nombre)

    def categoria(self, nombre='Tapas y sellado'):
        return CategoriaInsumo.objects.get(nombre=nombre)

    def crear_producto(self, nombre='Botellón 20L', presentacion='BOT', unidad_medida=None):
        return Producto.objects.create(
            nombre=nombre, presentacion=presentacion,
            unidad_medida=unidad_medida or self.unidad('unidad'),
        )

    def crear_insumo(self, nombre='Tapa plástica', stock_actual=Decimal('50'),
                      stock_minimo=Decimal('10'), categoria=None, unidad_medida=None):
        return Insumo.objects.create(
            nombre=nombre,
            categoria=categoria or self.categoria('Tapas y sellado'),
            unidad_medida=unidad_medida or self.unidad('unidad'),
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


class FormularioProduccionTests(ProduccionTestMixin, TestCase):
    """Tarea 5: tras un POST inválido, el formulario debe volver con todo lo
    digitado y el error debe verse junto al campo, no solo en el banner.

    Nota: el bug original también incluía un desincronizo de TOTAL_FORMS
    causado por el JS de "Cargar receta" (removía filas del DOM sin
    decrementar el management form, generando filas fantasma en blanco al
    volver del servidor). Ese fix es solo de JavaScript — no ejecutable desde
    TestCase — y se verificó reproduciendo a mano el POST exacto que el
    navegador enviaría (ver produccion/MODULO_PRODUCCION.md, sesión de esta
    tarea) y corrigiendo produccion_form.html en consecuencia."""

    def setUp(self):
        self.admin = self.crear_admin()
        self.client.force_login(self.admin)
        self.producto = self.crear_producto()
        self.insumo = self.crear_insumo(stock_actual=Decimal('5'))

    def _post_stock_insuficiente(self):
        data = {
            'fecha': '2026-09-07',
            'lote': 'PROD-BUG-001',
            'producto': self.producto.pk,
            'cantidad_producida': 10,
            'observaciones': 'nota de prueba',
            'consumos-TOTAL_FORMS': '2',
            'consumos-INITIAL_FORMS': '0',
            'consumos-MIN_NUM_FORMS': '0',
            'consumos-MAX_NUM_FORMS': '1000',
            'consumos-0-insumo': self.insumo.pk,
            'consumos-0-cantidad': '999',
            'consumos-1-insumo': '',
            'consumos-1-cantidad': '',
        }
        return self.client.post(reverse('produccion:produccion_create'), data=data)

    def test_conserva_datos_del_formulario_tras_stock_insuficiente(self):
        response = self._post_stock_insuficiente()

        self.assertEqual(response.status_code, 200)
        html = response.content.decode('utf-8')
        self.assertIn('PROD-BUG-001', html)
        self.assertIn('nota de prueba', html)
        self.assertIn(f'value="{self.producto.pk}" selected', html)
        self.assertIn(f'value="{self.insumo.pk}" selected', html)
        self.assertIn('value="999"', html)

    def test_error_de_stock_aparece_junto_al_campo_ademas_del_banner(self):
        response = self._post_stock_insuficiente()

        mensajes = [str(m) for m in response.context['messages']]
        self.assertTrue(any('Stock insuficiente' in m for m in mensajes))

        formset = response.context['formset']
        self.assertIn('Stock insuficiente', formset.forms[0].errors.get('cantidad', [''])[0])


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
        otro_producto = self.crear_producto(nombre='Bolsa 300ml', presentacion='BIN')
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


class CatalogosTests(ProduccionTestMixin, TestCase):
    """CategoriaInsumo y UnidadMedida deben poder crecer desde el admin,
    sin migración de código (Tarea 1 y 2)."""

    def test_categoria_insumo_tiene_al_menos_8_activas(self):
        self.assertGreaterEqual(CategoriaInsumo.objects.filter(activo=True).count(), 8)

    def test_unidad_medida_incluye_las_unidades_pedidas(self):
        nombres = set(UnidadMedida.objects.values_list('nombre', flat=True))
        requeridas = {
            'unidad', 'millar', 'paquete', 'rollo', 'caja', 'bulto',
            'kilogramo', 'gramo', 'litro', 'mililitro', 'metro',
        }
        self.assertTrue(requeridas.issubset(nombres))

    def test_categoria_nueva_aparece_en_el_formulario_sin_tocar_codigo(self):
        from .forms import InsumoForm
        nueva = CategoriaInsumo.objects.create(nombre='Categoría de prueba', orden=99)
        form = InsumoForm()
        self.assertIn(nueva, form.fields['categoria'].queryset)


class InsumoFormValidacionTests(ProduccionTestMixin, TestCase):
    def test_no_se_puede_guardar_insumo_con_categoria_vacia(self):
        from .forms import InsumoForm
        form = InsumoForm(data={
            'nombre': 'Nuevo insumo', 'categoria': '',
            'unidad_medida': self.unidad('unidad').pk,
            'stock_actual': '0', 'stock_minimo': '0',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('categoria', form.errors)

    def test_no_se_puede_guardar_insumo_con_unidad_fuera_del_catalogo(self):
        from .forms import InsumoForm
        pk_inexistente = UnidadMedida.objects.order_by('-pk').first().pk + 1000
        form = InsumoForm(data={
            'nombre': 'Nuevo insumo', 'categoria': self.categoria().pk,
            'unidad_medida': pk_inexistente, 'stock_actual': '0', 'stock_minimo': '0',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('unidad_medida', form.errors)

    def test_bloquea_cambiar_unidad_si_ya_tiene_consumos_de_produccion(self):
        insumo = self.crear_insumo(unidad_medida=self.unidad('litro'))
        producto = self.crear_producto()
        admin = self.crear_admin(username='cesar_edit1')
        prod = Produccion.objects.create(
            fecha='2026-09-01', lote='PROD-EDIT', producto=producto,
            cantidad_producida=1, registrado_por=admin,
        )
        ConsumoInsumo.objects.create(produccion=prod, insumo=insumo, cantidad=Decimal('1'))

        from .forms import InsumoForm
        form = InsumoForm(instance=insumo, data={
            'nombre': insumo.nombre, 'categoria': insumo.categoria.pk,
            'unidad_medida': self.unidad('unidad').pk,
            'stock_actual': str(insumo.stock_actual), 'stock_minimo': str(insumo.stock_minimo),
        })
        self.assertFalse(form.is_valid())
        self.assertIn('unidad_medida', form.errors)

    def test_permite_editar_insumo_sin_cambiar_unidad_aunque_tenga_consumos(self):
        insumo = self.crear_insumo(unidad_medida=self.unidad('litro'))
        producto = self.crear_producto()
        admin = self.crear_admin(username='cesar_edit2')
        prod = Produccion.objects.create(
            fecha='2026-09-01', lote='PROD-EDIT2', producto=producto,
            cantidad_producida=1, registrado_por=admin,
        )
        ConsumoInsumo.objects.create(produccion=prod, insumo=insumo, cantidad=Decimal('1'))

        from .forms import InsumoForm
        form = InsumoForm(instance=insumo, data={
            'nombre': 'Nombre corregido', 'categoria': insumo.categoria.pk,
            'unidad_medida': insumo.unidad_medida.pk,
            'stock_actual': str(insumo.stock_actual), 'stock_minimo': str(insumo.stock_minimo),
        })
        self.assertTrue(form.is_valid())


class MensajeStockInsuficienteTests(ProduccionTestMixin, TestCase):
    def setUp(self):
        self.admin = self.crear_admin()
        self.client.force_login(self.admin)
        self.producto = self.crear_producto()
        self.insumo = self.crear_insumo(stock_actual=Decimal('5'), unidad_medida=self.unidad('rollo'))

    def test_mensaje_muestra_la_misma_unidad_en_disponible_y_requerido(self):
        data = {
            'fecha': '2026-09-01', 'lote': 'PROD-MSG', 'producto': self.producto.pk,
            'cantidad_producida': 1, 'observaciones': '',
            'consumos-TOTAL_FORMS': '1', 'consumos-INITIAL_FORMS': '0',
            'consumos-MIN_NUM_FORMS': '0', 'consumos-MAX_NUM_FORMS': '1000',
            'consumos-0-insumo': self.insumo.pk, 'consumos-0-cantidad': '999',
        }
        response = self.client.post(reverse('produccion:produccion_create'), data=data)

        mensajes = [str(m) for m in response.context['messages']]
        self.assertTrue(any(
            'disponible 5.00 rollo' in m and 'requerido 999 rollo' in m for m in mensajes
        ), mensajes)


class ProductoFormTests(ProduccionTestMixin, TestCase):
    def test_contenido_unidad_solo_ofrece_unidades_de_volumen_o_masa(self):
        from .forms import ProductoForm
        form = ProductoForm()
        nombres = set(form.fields['contenido_unidad'].queryset.values_list('nombre', flat=True))
        self.assertEqual(nombres, {'litro', 'mililitro', 'gramo', 'kilogramo'})

    def test_no_se_puede_guardar_producto_con_presentacion_arbitraria(self):
        from .forms import ProductoForm
        form = ProductoForm(data={
            'nombre': 'Producto raro', 'presentacion': 'XXX',
            'contenido_cantidad': '', 'contenido_unidad': '', 'unidades_por_empaque': '',
            'unidad_medida': self.unidad('unidad').pk, 'activo': True,
        })
        self.assertFalse(form.is_valid())
        self.assertIn('presentacion', form.errors)


class NavegacionRecetasTests(ProduccionTestMixin, TestCase):
    """Tarea 4: Recetas debe ser alcanzable por clics desde el menú lateral."""

    def setUp(self):
        self.admin = self.crear_admin()
        self.client.force_login(self.admin)

    def test_sidebar_incluye_enlace_a_recetas(self):
        response = self.client.get(reverse('produccion:producto_list'))
        self.assertContains(response, reverse('produccion:receta_list'))
        self.assertContains(response, 'Recetas')


from datetime import date
from django.core.exceptions import ValidationError
from reportes.models import CierreAnual


class BloqueoPorCierreAnualTests(TestCase):
    def setUp(self):
        self.admin = Usuario.objects.create_user(username='admin_bloqueo', password='brisas2024', rol='ADMIN')
        self.producto = Producto.objects.create(nombre='Bolsa test', presentacion=Producto.Presentacion.BOLSA_INDIVIDUAL)
        CierreAnual.objects.create(anio=2025, cerrado_por=self.admin)

    def test_produccion_en_anio_cerrado_falla_full_clean(self):
        registro = Produccion(
            fecha=date(2025, 6, 1), lote='LOTE-BLOQUEO-1', producto=self.producto,
            cantidad_producida=10, registrado_por=self.admin,
        )
        with self.assertRaises(ValidationError):
            registro.full_clean()

    def test_produccion_en_anio_abierto_no_falla(self):
        registro = Produccion(
            fecha=date(2026, 6, 1), lote='LOTE-BLOQUEO-2', producto=self.producto,
            cantidad_producida=10, registrado_por=self.admin,
        )
        registro.full_clean()  # no debe lanzar

    def test_compra_insumo_en_anio_cerrado_falla(self):
        insumo = Insumo.objects.create(
            nombre='Insumo test',
            categoria=CategoriaInsumo.objects.create(nombre='Cat test'),
            unidad_medida=UnidadMedida.objects.create(nombre='unidad test'),
        )
        compra = CompraInsumo(
            fecha=date(2025, 6, 1), insumo=insumo, cantidad=5,
            precio_unitario=1000, registrado_por=self.admin,
        )
        with self.assertRaises(ValidationError):
            compra.full_clean()

    def test_regalia_en_anio_cerrado_falla(self):
        regalia = Regalia(
            fecha=date(2025, 6, 1), producto=self.producto, cantidad=1,
            registrado_por=self.admin,
        )
        with self.assertRaises(ValidationError):
            regalia.full_clean()
