from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from produccion.models import Producto

from .forms import ClienteForm, EntregaForm
from .models import Averia, Cliente, Credito, Entrega, Planilla, PrecioPorCategoria

Usuario = get_user_model()


class PrecioPorCategoriaTests(TestCase):
    """Regla de negocio central: el precio es por categoría (REG/MAY), nunca por
    cliente individual (sección 9, regla 2 de CLAUDE.md)."""

    def setUp(self):
        self.producto = Producto.objects.create(nombre='Bolsa 300ml', presentacion='B3C')
        self.precio_reg = PrecioPorCategoria.objects.create(
            categoria=Cliente.Categoria.REGULAR, producto=self.producto, precio=Decimal('500.00')
        )
        self.precio_may = PrecioPorCategoria.objects.create(
            categoria=Cliente.Categoria.MAYORISTA, producto=self.producto, precio=Decimal('400.00')
        )
        self.cliente_reg_1 = Cliente.objects.create(nombre='Tienda A', categoria=Cliente.Categoria.REGULAR)
        self.cliente_reg_2 = Cliente.objects.create(nombre='Tienda B', categoria=Cliente.Categoria.REGULAR)

    def test_dos_clientes_de_la_misma_categoria_comparten_precio(self):
        precio_1 = PrecioPorCategoria.objects.get(categoria=self.cliente_reg_1.categoria, producto=self.producto)
        precio_2 = PrecioPorCategoria.objects.get(categoria=self.cliente_reg_2.categoria, producto=self.producto)
        self.assertEqual(precio_1.precio, precio_2.precio)

    def test_categorias_distintas_pueden_tener_precios_distintos(self):
        self.assertNotEqual(self.precio_reg.precio, self.precio_may.precio)

    def test_no_puede_haber_dos_precios_para_la_misma_categoria_y_producto(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                PrecioPorCategoria.objects.create(
                    categoria=Cliente.Categoria.REGULAR, producto=self.producto, precio=Decimal('999.00')
                )

    def test_entregaform_ignora_precio_manipulado_y_usa_el_de_la_categoria(self):
        """El precio_unitario que llega en el POST no es de confianza: el servidor
        debe reemplazarlo por el vigente para la categoría del cliente."""
        form = EntregaForm(data={
            'cliente': self.cliente_reg_1.pk,
            'producto': self.producto.pk,
            'cantidad': 10,
            'precio_unitario': '999999.00',
            'modalidad_pago': Entrega.ModalidadPago.EFECTIVO,
            'devolucion': 0,
        })
        self.assertTrue(form.is_valid(), form.errors)
        entrega = form.save(commit=False)
        self.assertEqual(entrega.precio_unitario, self.precio_reg.precio)

    def test_entregaform_rechaza_producto_sin_precio_configurado_para_la_categoria(self):
        producto_sin_precio = Producto.objects.create(nombre='Hielo', presentacion='HIE')
        form = EntregaForm(data={
            'cliente': self.cliente_reg_1.pk,
            'producto': producto_sin_precio.pk,
            'cantidad': 1,
            'precio_unitario': '100.00',
            'modalidad_pago': Entrega.ModalidadPago.EFECTIVO,
            'devolucion': 0,
        })
        self.assertFalse(form.is_valid())
        self.assertIn('__all__', form.errors)


class CreditoAutoGeneracionTests(TestCase):
    """Regla de negocio: Credito se genera automáticamente 1:1 con Entrega cuando
    modalidad_pago='CRE' (sección 9, regla 3 de CLAUDE.md)."""

    def setUp(self):
        self.distribuidor = Usuario.objects.create_user(username='nico', password='brisas2024', rol='DIST')
        self.producto = Producto.objects.create(nombre='Botellón', presentacion='BOT')
        PrecioPorCategoria.objects.create(
            categoria=Cliente.Categoria.REGULAR, producto=self.producto, precio=Decimal('3000.00')
        )
        self.cliente = Cliente.objects.create(nombre='Tienda', categoria=Cliente.Categoria.REGULAR)
        self.planilla = Planilla.objects.create(fecha=date.today(), distribuidor=self.distribuidor)

    def _post_agregar_entrega(self, modalidad, cantidad=5, devolucion=0):
        self.client.force_login(self.distribuidor)
        return self.client.post(
            reverse('distribucion:ruta_planilla', kwargs={'pk': self.planilla.pk}),
            {
                'accion': 'agregar_entrega',
                'cliente': self.cliente.pk,
                'producto': self.producto.pk,
                'cantidad': cantidad,
                'precio_unitario': '3000.00',
                'modalidad_pago': modalidad,
                'devolucion': devolucion,
            },
        )

    def test_credito_se_crea_automaticamente_con_modalidad_credito(self):
        self._post_agregar_entrega(Entrega.ModalidadPago.CREDITO)
        entrega = Entrega.objects.get(planilla=self.planilla)
        self.assertTrue(Credito.objects.filter(entrega=entrega).exists())
        credito = entrega.credito
        self.assertEqual(credito.monto, entrega.subtotal)
        self.assertEqual(credito.saldo_pendiente, entrega.subtotal)
        self.assertFalse(credito.pagado)
        self.assertEqual(credito.cliente, self.cliente)

    def test_no_se_crea_credito_con_modalidad_efectivo(self):
        self._post_agregar_entrega(Entrega.ModalidadPago.EFECTIVO)
        entrega = Entrega.objects.get(planilla=self.planilla)
        self.assertFalse(Credito.objects.filter(entrega=entrega).exists())

    def test_no_se_crea_credito_con_modalidad_nequi(self):
        self._post_agregar_entrega(Entrega.ModalidadPago.NEQUI)
        entrega = Entrega.objects.get(planilla=self.planilla)
        self.assertFalse(Credito.objects.filter(entrega=entrega).exists())

    def test_credito_es_relacion_uno_a_uno_con_entrega(self):
        self._post_agregar_entrega(Entrega.ModalidadPago.CREDITO)
        entrega = Entrega.objects.get(planilla=self.planilla)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Credito.objects.create(
                    cliente=self.cliente, entrega=entrega, monto=Decimal('1'), saldo_pendiente=Decimal('1')
                )


class APIDistribucionTests(TestCase):
    """Cobertura de los 5 endpoints DRF usados por la sincronización híbrida
    (localStorage + Axios) del distribuidor."""

    def setUp(self):
        self.client = APIClient()
        self.dist_user = Usuario.objects.create_user(username='nico', password='brisas2024', rol='DIST')
        self.prod_user = Usuario.objects.create_user(username='cesar', password='brisas2024', rol='PROD')
        self.producto = Producto.objects.create(nombre='Botellón', presentacion='BOT')
        PrecioPorCategoria.objects.create(
            categoria=Cliente.Categoria.REGULAR, producto=self.producto, precio=Decimal('3000.00')
        )
        self.cliente = Cliente.objects.create(nombre='Tienda', categoria=Cliente.Categoria.REGULAR)

    # -- planilla-activa --

    def test_planilla_activa_get_sin_planilla_devuelve_404(self):
        self.client.force_authenticate(self.dist_user)
        resp = self.client.get(reverse('distribucion:api_planilla_activa'))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_planilla_activa_post_crea_planilla_del_dia(self):
        self.client.force_authenticate(self.dist_user)
        resp = self.client.post(reverse('distribucion:api_planilla_activa'))
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Planilla.objects.filter(distribuidor=self.dist_user, fecha=date.today()).exists())

    def test_planilla_activa_post_es_idempotente_el_mismo_dia(self):
        self.client.force_authenticate(self.dist_user)
        self.client.post(reverse('distribucion:api_planilla_activa'))
        resp = self.client.post(reverse('distribucion:api_planilla_activa'))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(Planilla.objects.filter(distribuidor=self.dist_user).count(), 1)

    # -- permisos compartidos por los 5 endpoints --

    def test_rol_produccion_no_puede_usar_la_api_de_distribucion(self):
        self.client.force_authenticate(self.prod_user)
        resp = self.client.get(reverse('distribucion:api_clientes'))
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_usuario_no_autenticado_no_puede_usar_la_api(self):
        resp = self.client.get(reverse('distribucion:api_productos'))
        self.assertIn(resp.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))

    # -- entregas --

    def test_entrega_create_api_crea_credito_si_modalidad_es_credito(self):
        self.client.force_authenticate(self.dist_user)
        planilla = Planilla.objects.create(distribuidor=self.dist_user, fecha=date.today())
        resp = self.client.post(reverse('distribucion:api_entrega_create'), {
            'planilla': planilla.pk,
            'cliente': self.cliente.pk,
            'producto': self.producto.pk,
            'cantidad': 4,
            'precio_unitario': '3000.00',
            'modalidad_pago': Entrega.ModalidadPago.CREDITO,
            'devolucion': 0,
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        entrega = Entrega.objects.get(pk=resp.data['id'])
        self.assertTrue(Credito.objects.filter(entrega=entrega).exists())

    def test_entrega_create_api_datos_invalidos_devuelve_400(self):
        self.client.force_authenticate(self.dist_user)
        resp = self.client.post(reverse('distribucion:api_entrega_create'), {})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    # -- averias --

    def test_averia_create_api(self):
        self.client.force_authenticate(self.dist_user)
        planilla = Planilla.objects.create(distribuidor=self.dist_user, fecha=date.today())
        resp = self.client.post(reverse('distribucion:api_averia_create'), {
            'planilla': planilla.pk,
            'producto': self.producto.pk,
            'cantidad': 2,
            'descripcion': 'rotura',
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Averia.objects.filter(planilla=planilla).exists())

    # -- clientes --

    def test_cliente_list_api_incluye_precios_de_su_categoria(self):
        self.client.force_authenticate(self.dist_user)
        resp = self.client.get(reverse('distribucion:api_clientes'))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        cliente_data = next(c for c in resp.data if c['id'] == self.cliente.pk)
        self.assertEqual(len(cliente_data['precios']), 1)
        self.assertEqual(Decimal(cliente_data['precios'][0]['precio']), Decimal('3000.00'))

    def test_cliente_list_api_excluye_inactivos(self):
        Cliente.objects.create(nombre='Cerrado', categoria=Cliente.Categoria.REGULAR, activo=False)
        self.client.force_authenticate(self.dist_user)
        resp = self.client.get(reverse('distribucion:api_clientes'))
        nombres = [c['nombre'] for c in resp.data]
        self.assertNotIn('Cerrado', nombres)

    # -- productos --

    def test_producto_list_api_excluye_inactivos(self):
        Producto.objects.create(nombre='Descontinuado', presentacion='HIE', activo=False)
        self.client.force_authenticate(self.dist_user)
        resp = self.client.get(reverse('distribucion:api_productos'))
        nombres = [p['nombre'] for p in resp.data]
        self.assertNotIn('Descontinuado', nombres)


class SeguridadEntregaAveriaAPITests(TestCase):
    """D-02 (IDOR crítico): la API de sync no validaba que `planilla` en el
    POST perteneciera al distribuidor autenticado — cualquier DIST podía
    crear entregas/averías en la planilla de otro. Hallazgo de QA exploratoria
    (proyecto-final-26), sesión 2026-09-07."""

    def setUp(self):
        self.client = APIClient()
        self.dist_a = Usuario.objects.create_user(username='nico', password='brisas2024', rol='DIST')
        self.dist_b = Usuario.objects.create_user(username='pedro', password='brisas2024', rol='DIST')
        self.producto = Producto.objects.create(nombre='Botellón', presentacion='BOT')
        PrecioPorCategoria.objects.create(
            categoria=Cliente.Categoria.REGULAR, producto=self.producto, precio=Decimal('3000.00')
        )
        self.cliente = Cliente.objects.create(nombre='Tienda', categoria=Cliente.Categoria.REGULAR)
        self.planilla_de_b = Planilla.objects.create(distribuidor=self.dist_b, fecha=date.today())

    def test_dist_no_puede_crear_entrega_en_planilla_de_otro_distribuidor(self):
        self.client.force_authenticate(self.dist_a)
        resp = self.client.post(reverse('distribucion:api_entrega_create'), {
            'planilla': self.planilla_de_b.pk,
            'cliente': self.cliente.pk,
            'producto': self.producto.pk,
            'cantidad': 2,
            'precio_unitario': '3000.00',
            'modalidad_pago': Entrega.ModalidadPago.EFECTIVO,
            'devolucion': 0,
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Entrega.objects.filter(planilla=self.planilla_de_b).exists())

    def test_dist_no_puede_crear_averia_en_planilla_de_otro_distribuidor(self):
        self.client.force_authenticate(self.dist_a)
        resp = self.client.post(reverse('distribucion:api_averia_create'), {
            'planilla': self.planilla_de_b.pk,
            'producto': self.producto.pk,
            'cantidad': 1,
            'descripcion': 'rotura',
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Averia.objects.filter(planilla=self.planilla_de_b).exists())

    def test_dist_si_puede_crear_entrega_en_su_propia_planilla(self):
        self.client.force_authenticate(self.dist_b)
        resp = self.client.post(reverse('distribucion:api_entrega_create'), {
            'planilla': self.planilla_de_b.pk,
            'cliente': self.cliente.pk,
            'producto': self.producto.pk,
            'cantidad': 2,
            'precio_unitario': '3000.00',
            'modalidad_pago': Entrega.ModalidadPago.EFECTIVO,
            'devolucion': 0,
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)


class PlanillaEstadoBloqueaEdicionTests(TestCase):
    """D-03: PlanillaRutaView.post no verificaba planilla.estado antes de
    agregar entrega/avería — se podía seguir editando una planilla ya
    VALIDADA por el admin. Hallazgo de QA exploratoria, sesión 2026-09-07."""

    def setUp(self):
        self.distribuidor = Usuario.objects.create_user(username='nico', password='brisas2024', rol='DIST')
        self.producto = Producto.objects.create(nombre='Botellón', presentacion='BOT')
        PrecioPorCategoria.objects.create(
            categoria=Cliente.Categoria.REGULAR, producto=self.producto, precio=Decimal('3000.00')
        )
        self.cliente = Cliente.objects.create(nombre='Tienda', categoria=Cliente.Categoria.REGULAR)
        self.planilla_validada = Planilla.objects.create(
            distribuidor=self.distribuidor, fecha=date.today(), estado=Planilla.Estado.VALIDADA,
        )

    def _post(self, planilla, data):
        self.client.force_login(self.distribuidor)
        return self.client.post(
            reverse('distribucion:ruta_planilla', kwargs={'pk': planilla.pk}), data,
        )

    def test_no_se_puede_agregar_entrega_a_planilla_validada(self):
        self._post(self.planilla_validada, {
            'accion': 'agregar_entrega',
            'cliente': self.cliente.pk,
            'producto': self.producto.pk,
            'cantidad': 2,
            'precio_unitario': '3000.00',
            'modalidad_pago': Entrega.ModalidadPago.EFECTIVO,
            'devolucion': 0,
        })
        self.assertFalse(Entrega.objects.filter(planilla=self.planilla_validada).exists())

    def test_no_se_puede_agregar_averia_a_planilla_validada(self):
        self._post(self.planilla_validada, {
            'accion': 'agregar_averia', 'producto': self.producto.pk, 'cantidad': 1, 'descripcion': 'x',
        })
        self.assertFalse(Averia.objects.filter(planilla=self.planilla_validada).exists())

    def test_no_se_puede_agregar_entrega_a_planilla_pendiente_de_validacion(self):
        planilla_pendiente = Planilla.objects.create(
            distribuidor=self.distribuidor, fecha=date(2026, 1, 2),
            estado=Planilla.Estado.PENDIENTE_VALIDACION,
        )
        self._post(planilla_pendiente, {
            'accion': 'agregar_entrega',
            'cliente': self.cliente.pk,
            'producto': self.producto.pk,
            'cantidad': 2,
            'precio_unitario': '3000.00',
            'modalidad_pago': Entrega.ModalidadPago.EFECTIVO,
            'devolucion': 0,
        })
        self.assertFalse(Entrega.objects.filter(planilla=planilla_pendiente).exists())

    def test_se_puede_agregar_entrega_a_planilla_abierta(self):
        planilla_abierta = Planilla.objects.create(
            distribuidor=self.distribuidor, fecha=date(2026, 1, 1), estado=Planilla.Estado.ABIERTA,
        )
        self._post(planilla_abierta, {
            'accion': 'agregar_entrega',
            'cliente': self.cliente.pk,
            'producto': self.producto.pk,
            'cantidad': 2,
            'precio_unitario': '3000.00',
            'modalidad_pago': Entrega.ModalidadPago.EFECTIVO,
            'devolucion': 0,
        })
        self.assertTrue(Entrega.objects.filter(planilla=planilla_abierta).exists())


class ClienteFormAutorizaDatosTests(TestCase):
    """D-04: `autoriza_datos` (Ley 1581/2012) no era obligatorio en el
    ModelForm — trampa clásica de Django: `BooleanField.formfield()` fuerza
    `required=False` sin importar el `blank` del modelo. Hallazgo de QA
    exploratoria, sesión 2026-09-07."""

    def test_autoriza_datos_es_obligatorio(self):
        form = ClienteForm(data={
            'nombre': 'Tienda Nueva',
            'telefono': '',
            'direccion': '',
            'categoria': Cliente.Categoria.REGULAR,
            'activo': True,
            # autoriza_datos deliberadamente omitido — como un checkbox sin marcar
        })
        self.assertFalse(form.is_valid())
        self.assertIn('autoriza_datos', form.errors)

    def test_cliente_se_crea_si_autoriza_datos_esta_marcado(self):
        form = ClienteForm(data={
            'nombre': 'Tienda Nueva',
            'telefono': '',
            'direccion': '',
            'categoria': Cliente.Categoria.REGULAR,
            'autoriza_datos': True,
            'activo': True,
        })
        self.assertTrue(form.is_valid(), form.errors)


from reportes.models import CierreAnual


class BloqueoPorCierreAnualTests(TestCase):
    def setUp(self):
        self.admin = Usuario.objects.create_user(username='admin_bloqueo_dist', password='brisas2024', rol='ADMIN')
        self.distribuidor = Usuario.objects.create_user(username='dist_bloqueo', password='brisas2024', rol='DIST')
        self.producto = Producto.objects.create(nombre='Bolsa test dist', presentacion=Producto.Presentacion.BOLSA_INDIVIDUAL)
        self.cliente = Cliente.objects.create(nombre='Cliente bloqueo', categoria='REG')
        CierreAnual.objects.create(anio=2025, cerrado_por=self.admin)

    def test_planilla_en_anio_cerrado_falla_full_clean(self):
        planilla = Planilla(fecha=date(2025, 6, 1), distribuidor=self.distribuidor)
        with self.assertRaises(ValidationError):
            planilla.full_clean()

    def test_planilla_en_anio_abierto_no_falla(self):
        planilla = Planilla(fecha=date(2026, 6, 1), distribuidor=self.distribuidor)
        planilla.full_clean()  # no debe lanzar

    def test_entrega_con_planilla_de_anio_cerrado_falla(self):
        planilla = Planilla.objects.create(fecha=date(2025, 6, 1), distribuidor=self.distribuidor)
        entrega = Entrega(
            planilla=planilla, cliente=self.cliente, producto=self.producto,
            cantidad=1, precio_unitario=1000, modalidad_pago='EFE',
        )
        with self.assertRaises(ValidationError):
            entrega.full_clean()

    def test_averia_con_planilla_de_anio_cerrado_falla(self):
        planilla = Planilla.objects.create(fecha=date(2025, 6, 1), distribuidor=self.distribuidor)
        averia = Averia(planilla=planilla, producto=self.producto, cantidad=1)
        with self.assertRaises(ValidationError):
            averia.full_clean()

    def test_entrega_sin_planilla_asignada_no_falla_por_cierre(self):
        # Simula el momento dentro de is_valid() en PlanillaRutaView, antes de
        # asignar `entrega.planilla`: no debe reventar con RelatedObjectDoesNotExist.
        entrega = Entrega(
            cliente=self.cliente, producto=self.producto,
            cantidad=1, precio_unitario=1000, modalidad_pago='EFE',
        )
        # full_clean() completo fallaría por 'planilla' requerido (no seteado);
        # probamos clean() aislado, que es lo que nos interesa acá.
        entrega.clean()  # no debe lanzar ValidationError por el chequeo de cierre


class PlanillaRutaViewCierreAnualTests(TestCase):
    def setUp(self):
        self.admin = Usuario.objects.create_user(username='admin_ruta_cierre', password='brisas2024', rol='ADMIN')
        self.distribuidor = Usuario.objects.create_user(username='dist_ruta_cierre', password='brisas2024', rol='DIST')
        self.cliente = Cliente.objects.create(nombre='Cliente ruta cierre', categoria='REG')
        self.producto = Producto.objects.create(nombre='Bolsa ruta cierre', presentacion=Producto.Presentacion.BOLSA_INDIVIDUAL)
        PrecioPorCategoria.objects.create(categoria='REG', producto=self.producto, precio=1000)
        CierreAnual.objects.create(anio=2025, cerrado_por=self.admin)
        self.planilla = Planilla.objects.create(
            fecha=date(2025, 6, 1), distribuidor=self.distribuidor, estado=Planilla.Estado.ABIERTA,
        )
        self.client.force_login(self.distribuidor)

    def test_agregar_entrega_en_planilla_de_anio_cerrado_es_rechazado(self):
        url = reverse('distribucion:ruta_planilla', kwargs={'pk': self.planilla.pk})
        resp = self.client.post(url, {
            'accion': 'agregar_entrega',
            'cliente': self.cliente.pk, 'producto': self.producto.pk,
            'cantidad': 1, 'precio_unitario': 1000, 'modalidad_pago': 'EFE', 'devolucion': 0,
        })
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(self.planilla.entregas.count(), 0)

    def test_agregar_averia_en_planilla_de_anio_cerrado_es_rechazado(self):
        url = reverse('distribucion:ruta_planilla', kwargs={'pk': self.planilla.pk})
        resp = self.client.post(url, {
            'accion': 'agregar_averia',
            'producto': self.producto.pk, 'cantidad': 1, 'descripcion': 'test',
        })
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(self.planilla.averias.count(), 0)

    def test_agregar_entrega_en_planilla_de_anio_abierto_funciona(self):
        planilla_abierta = Planilla.objects.create(
            fecha=date(2026, 6, 1), distribuidor=self.distribuidor, estado=Planilla.Estado.ABIERTA,
        )
        url = reverse('distribucion:ruta_planilla', kwargs={'pk': planilla_abierta.pk})
        resp = self.client.post(url, {
            'accion': 'agregar_entrega',
            'cliente': self.cliente.pk, 'producto': self.producto.pk,
            'cantidad': 1, 'precio_unitario': 1000, 'modalidad_pago': 'EFE', 'devolucion': 0,
        })
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(planilla_abierta.entregas.count(), 1)
