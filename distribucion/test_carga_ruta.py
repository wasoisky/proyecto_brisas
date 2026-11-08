"""Cargue de la ruta, devolución por ruta y conciliación.

Flujo: el distribuidor registra lo que carga en el camión (CargaRuta); a medida que
entrega y reporta averías, "queda" baja; al cerrar la ruta registra lo que devuelve
a planta y el ADMIN ve la conciliación (cargado - entregado - averiado - devuelto).
El stock disponible en planta se calcula al vuelo:
producido - cargado + devuelto - regalías.
"""
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from produccion.models import Produccion, Producto, Regalia
from reportes.models import CierreAnual
from usuarios.models import Usuario

from .conciliacion import disponible_en_planta, resumen_planilla
from .models import Averia, CargaRuta, Cliente, Entrega, Planilla, PrecioPorCategoria


class CargaBase(TestCase):
    def setUp(self):
        self.admin = Usuario.objects.create_user(username='edwin', password='x', rol='ADMIN')
        self.dist = Usuario.objects.create_user(username='nico', password='x', rol='DIST')
        self.otro = Usuario.objects.create_user(username='cami', password='x', rol='DIST')
        self.prod_user = Usuario.objects.create_user(username='wil', password='x', rol='PROD')
        self.botellon = Producto.objects.create(nombre='Botellón', presentacion='BOT')
        self.paca = Producto.objects.create(nombre='Paca', presentacion='PAC')
        PrecioPorCategoria.objects.create(categoria='REG', producto=self.botellon, precio=Decimal('3000'))
        PrecioPorCategoria.objects.create(categoria='REG', producto=self.paca, precio=Decimal('10000'))
        self.cliente = Cliente.objects.create(nombre='Tienda', categoria='REG', autoriza_datos=True)
        self.planilla = Planilla.objects.create(distribuidor=self.dist, fecha=date.today())
        self.url = reverse('distribucion:ruta_planilla', args=[self.planilla.pk])

    def entrega(self, producto, cantidad, planilla=None, devolucion=0):
        return Entrega.objects.create(
            planilla=planilla or self.planilla, cliente=self.cliente, producto=producto,
            cantidad=cantidad, precio_unitario=Decimal('1000'), modalidad_pago='EFE',
            devolucion=devolucion,
        )

    def averia(self, producto, cantidad):
        return Averia.objects.create(planilla=self.planilla, producto=producto, cantidad=cantidad)

    def cargar(self, producto, cantidad, devuelta=None):
        return CargaRuta.objects.create(
            planilla=self.planilla, producto=producto, cantidad_cargada=cantidad, cantidad_devuelta=devuelta,
        )


class CargaRutaModeloTests(CargaBase):
    def test_un_producto_solo_se_carga_una_vez_por_planilla(self):
        self.cargar(self.botellon, 10)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.cargar(self.botellon, 5)

    def test_la_cantidad_cargada_debe_ser_al_menos_uno(self):
        c = CargaRuta(planilla=self.planilla, producto=self.botellon, cantidad_cargada=0)
        with self.assertRaises(ValidationError):
            c.full_clean()

    def test_la_devuelta_no_puede_superar_la_cargada(self):
        c = CargaRuta(planilla=self.planilla, producto=self.botellon, cantidad_cargada=5, cantidad_devuelta=6)
        with self.assertRaises(ValidationError):
            c.full_clean()

    def test_anio_cerrado_bloquea_la_carga(self):
        CierreAnual.objects.create(anio=self.planilla.fecha.year, cerrado_por=self.admin)
        c = CargaRuta(planilla=self.planilla, producto=self.botellon, cantidad_cargada=5)
        with self.assertRaises(ValidationError):
            c.full_clean()


class ConciliacionTests(CargaBase):
    def test_resumen_calcula_queda_y_diferencia(self):
        self.cargar(self.botellon, 10, devuelta=3)
        self.entrega(self.botellon, 4)
        self.entrega(self.botellon, 2)
        self.averia(self.botellon, 1)
        fila = resumen_planilla(self.planilla)[0]
        self.assertEqual(fila['producto'], self.botellon)
        self.assertEqual(fila['cargado'], 10)
        self.assertEqual(fila['entregado'], 6)
        self.assertEqual(fila['averiado'], 1)
        self.assertEqual(fila['queda'], 3)
        self.assertEqual(fila['devuelto'], 3)
        self.assertEqual(fila['diferencia'], 0)

    def test_diferencia_positiva_es_faltante_y_negativa_sobrante(self):
        self.cargar(self.botellon, 10, devuelta=2)
        self.entrega(self.botellon, 6)
        self.averia(self.botellon, 1)           # queda 3, devolvió 2 -> falta 1
        self.assertEqual(resumen_planilla(self.planilla)[0]['diferencia'], 1)
        CargaRuta.objects.filter(planilla=self.planilla).update(cantidad_devuelta=5)  # sobran 2
        self.assertEqual(resumen_planilla(self.planilla)[0]['diferencia'], -2)

    def test_sin_devolucion_registrada_no_hay_diferencia(self):
        self.cargar(self.botellon, 10)
        fila = resumen_planilla(self.planilla)[0]
        self.assertIsNone(fila['devuelto'])
        self.assertIsNone(fila['diferencia'])
        self.assertEqual(fila['queda'], 10)

    def test_entregas_heredadas_con_devolucion_cuentan_neto(self):
        self.cargar(self.botellon, 10)
        self.entrega(self.botellon, 5, devolucion=2)
        self.assertEqual(resumen_planilla(self.planilla)[0]['entregado'], 3)

    def test_producto_entregado_sin_carga_aparece_con_cargado_cero(self):
        self.entrega(self.paca, 2)
        fila = [f for f in resumen_planilla(self.planilla) if f['producto'] == self.paca][0]
        self.assertEqual(fila['cargado'], 0)
        self.assertEqual(fila['entregado'], 2)
        self.assertEqual(fila['queda'], -2)

    def test_planilla_sin_movimientos_da_resumen_vacio(self):
        self.assertEqual(resumen_planilla(self.planilla), [])


class StockDisponibleTests(CargaBase):
    def _producir(self, producto, cantidad, lote):
        return Produccion.objects.create(
            fecha=date.today(), lote=lote, producto=producto, cantidad_producida=cantidad,
            registrado_por=self.prod_user,
        )

    def test_disponible_es_producido_menos_cargado_mas_devuelto_menos_regalias(self):
        prod = self._producir(self.botellon, 100, 'L1')
        self.cargar(self.botellon, 30, devuelta=5)
        Regalia.objects.create(
            fecha=date.today(), producto=self.botellon, produccion=prod, cantidad=2,
            destinatario='X', motivo='OBS', registrado_por=self.prod_user,
        )
        self.assertEqual(disponible_en_planta(self.botellon), 100 - 30 + 5 - 2)

    def test_producto_sin_movimientos_tiene_cero(self):
        self.assertEqual(disponible_en_planta(self.paca), 0)

    def test_las_cargas_de_todas_las_planillas_descuentan(self):
        self._producir(self.botellon, 50, 'L1')
        self.cargar(self.botellon, 10)
        otra = Planilla.objects.create(distribuidor=self.otro, fecha=date.today())
        CargaRuta.objects.create(planilla=otra, producto=self.botellon, cantidad_cargada=15)
        self.assertEqual(disponible_en_planta(self.botellon), 25)

    def test_el_listado_de_productos_muestra_el_disponible(self):
        self._producir(self.botellon, 40, 'L1')
        self.cargar(self.botellon, 15)
        self.client.force_login(self.prod_user)
        resp = self.client.get(reverse('produccion:producto_list'))
        por_nombre = {p.nombre: p.disponible for p in resp.context['productos']}
        self.assertEqual(por_nombre['Botellón'], 25)


class GuardarCargaVistaTests(CargaBase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.dist)

    def _guardar(self, producto, cantidad, url=None):
        return self.client.post(url or self.url, {
            'accion': 'guardar_carga', 'producto': producto.pk, 'cantidad': cantidad,
        })

    def test_el_distribuidor_registra_su_carga(self):
        self._guardar(self.botellon, 12)
        self.assertEqual(CargaRuta.objects.get().cantidad_cargada, 12)

    def test_volver_a_guardar_el_mismo_producto_reemplaza_la_cantidad(self):
        self._guardar(self.botellon, 12)
        self._guardar(self.botellon, 20)
        self.assertEqual(CargaRuta.objects.count(), 1)
        self.assertEqual(CargaRuta.objects.get().cantidad_cargada, 20)

    def test_cantidad_invalida_se_rechaza(self):
        for malo in ('0', '-3', 'abc', ''):
            self._guardar(self.botellon, malo)
        self.assertEqual(CargaRuta.objects.count(), 0)

    def test_no_se_puede_bajar_la_carga_por_debajo_de_lo_ya_entregado_y_averiado(self):
        self.cargar(self.botellon, 10)
        self.entrega(self.botellon, 6)
        self.averia(self.botellon, 2)
        self._guardar(self.botellon, 7)        # 6 + 2 = 8 ya salieron
        self.assertEqual(CargaRuta.objects.get().cantidad_cargada, 10)
        self._guardar(self.botellon, 8)
        self.assertEqual(CargaRuta.objects.get().cantidad_cargada, 8)

    def test_planilla_no_abierta_no_acepta_carga(self):
        self.planilla.estado = Planilla.Estado.PENDIENTE_VALIDACION
        self.planilla.save()
        self._guardar(self.botellon, 5)
        self.assertEqual(CargaRuta.objects.count(), 0)

    def test_un_distribuidor_no_carga_en_la_planilla_de_otro(self):
        ajena = Planilla.objects.create(distribuidor=self.otro, fecha=date.today())
        resp = self._guardar(self.botellon, 5, url=reverse('distribucion:ruta_planilla', args=[ajena.pk]))
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(CargaRuta.objects.count(), 0)

    def test_anio_cerrado_no_acepta_carga(self):
        CierreAnual.objects.create(anio=self.planilla.fecha.year, cerrado_por=self.admin)
        self._guardar(self.botellon, 5)
        self.assertEqual(CargaRuta.objects.count(), 0)

    def test_un_nombre_de_producto_malicioso_no_puede_cerrar_el_script(self):
        # El JSON de la pantalla va dentro de <script>: '<' y '>' deben ir escapados.
        malo = Producto.objects.create(nombre='</script><script>alert(1)</script>', presentacion='BOT')
        self.cargar(malo, 3)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, '</script><script>alert(1)</script>')

    def test_la_pantalla_de_ruta_trae_el_resumen_del_camion(self):
        self.cargar(self.botellon, 10)
        self.entrega(self.botellon, 4)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        fila = resp.context['resumen'][0]
        self.assertEqual((fila['cargado'], fila['entregado'], fila['queda']), (10, 4, 6))


class CierreConDevolucionTests(CargaBase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.dist)
        self.cargar(self.botellon, 10)
        self.cargar(self.paca, 5)

    def _enviar(self, **devueltos):
        datos = {'accion': 'enviar_validacion'}
        datos.update({f'devuelto_{k}': v for k, v in devueltos.items()})
        return self.client.post(self.url, datos)

    def _estado(self):
        self.planilla.refresh_from_db()
        return self.planilla.estado

    def test_enviar_guarda_la_devolucion_y_cambia_el_estado(self):
        self._enviar(**{str(self.botellon.pk): 3, str(self.paca.pk): 0})
        self.assertEqual(self._estado(), Planilla.Estado.PENDIENTE_VALIDACION)
        self.assertEqual(CargaRuta.objects.get(producto=self.botellon).cantidad_devuelta, 3)
        self.assertEqual(CargaRuta.objects.get(producto=self.paca).cantidad_devuelta, 0)

    def test_si_falta_la_devolucion_de_un_producto_no_se_envia(self):
        self._enviar(**{str(self.botellon.pk): 3})
        self.assertEqual(self._estado(), Planilla.Estado.ABIERTA)
        self.assertIsNone(CargaRuta.objects.get(producto=self.botellon).cantidad_devuelta)

    def test_devolucion_invalida_no_envia_ni_guarda_nada(self):
        for malo in ('-1', 'x', '11'):                     # 11 > 10 cargados
            self._enviar(**{str(self.botellon.pk): malo, str(self.paca.pk): 0})
        self.assertEqual(self._estado(), Planilla.Estado.ABIERTA)
        self.assertIsNone(CargaRuta.objects.get(producto=self.paca).cantidad_devuelta)

    def test_planilla_sin_carga_se_envia_como_antes(self):
        CargaRuta.objects.all().delete()
        self._enviar()
        self.assertEqual(self._estado(), Planilla.Estado.PENDIENTE_VALIDACION)


class ConciliacionAdminTests(CargaBase):
    def test_el_detalle_de_la_planilla_muestra_la_conciliacion(self):
        self.cargar(self.botellon, 10, devuelta=2)
        self.entrega(self.botellon, 6)
        self.planilla.estado = Planilla.Estado.PENDIENTE_VALIDACION
        self.planilla.save()
        self.client.force_login(self.admin)
        resp = self.client.get(reverse('distribucion:planilla_detail', args=[self.planilla.pk]))
        self.assertEqual(resp.status_code, 200)
        fila = resp.context['conciliacion'][0]
        self.assertEqual(fila['diferencia'], 2)
        self.assertContains(resp, 'Conciliación')
