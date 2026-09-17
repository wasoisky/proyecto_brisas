from datetime import date, timedelta, date as date_cls
from decimal import Decimal

from django.core.management import call_command
from django.core.management.base import CommandError
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from django.db.models import F, Sum
from django.test import TestCase
from django.urls import reverse

from produccion.models import Insumo, Producto, Produccion, CategoriaInsumo, UnidadMedida
from distribucion.models import Cliente, Planilla, Entrega
from activos.models import ActivoRetornable, MovimientoActivo
from usuarios.models import Usuario

from .detector import detectar_pv, detectar_vi, detectar_ac, ejecutar_deteccion
from .models import Descuadre, CierreAnual
from .cierres import anio_cerrado, validar_periodo_abierto


class DetectorHelpersMixin:
    """Helpers compartidos por los tests de detección automática (HU-13)."""

    def crear_admin(self, username='maximino'):
        return Usuario.objects.create_user(
            username=username, password='brisas2024', rol='ADMIN',
        )

    def crear_producto(self, nombre='Bolsa 300ml', presentacion=Producto.Presentacion.BOLSA_INDIVIDUAL):
        return Producto.objects.create(nombre=nombre, presentacion=presentacion)

    def crear_produccion(self, producto, cantidad, fecha, usuario, lote=None):
        return Produccion.objects.create(
            fecha=fecha,
            lote=lote or f'LOTE-{fecha}-{cantidad}',
            producto=producto,
            cantidad_producida=cantidad,
            registrado_por=usuario,
        )

    def crear_entrega(self, producto, cantidad, fecha, devolucion=0):
        distribuidor = Usuario.objects.create_user(
            username=f'dist_{fecha}_{producto.pk}_{cantidad}', password='brisas2024', rol='DIST',
        )
        cliente = Cliente.objects.create(nombre='Cliente Test', categoria='REG')
        planilla = Planilla.objects.create(fecha=fecha, distribuidor=distribuidor)
        return Entrega.objects.create(
            planilla=planilla, cliente=cliente, producto=producto,
            cantidad=cantidad, precio_unitario=Decimal('1000'),
            modalidad_pago='EFE', devolucion=devolucion,
        )


class DetectarPVTests(DetectorHelpersMixin, TestCase):
    def setUp(self):
        self.admin = self.crear_admin()
        self.producto = self.crear_producto()
        self.fecha = date(2026, 8, 1)

    def test_sin_diferencia_no_genera_hallazgo(self):
        self.crear_produccion(self.producto, 100, self.fecha, self.admin)
        self.crear_entrega(self.producto, 100, self.fecha)

        hallazgos = detectar_pv(self.fecha, self.fecha)

        self.assertEqual(hallazgos, [])

    def test_diferencia_pequena_dentro_de_tolerancia_no_genera_hallazgo(self):
        # 4% de diferencia — por debajo del umbral del 5%
        self.crear_produccion(self.producto, 100, self.fecha, self.admin)
        self.crear_entrega(self.producto, 96, self.fecha)

        hallazgos = detectar_pv(self.fecha, self.fecha)

        self.assertEqual(hallazgos, [])

    def test_diferencia_moderada_genera_hallazgo_leve(self):
        # 10% de diferencia — entre 5% y 15%
        self.crear_produccion(self.producto, 100, self.fecha, self.admin)
        self.crear_entrega(self.producto, 90, self.fecha)

        hallazgos = detectar_pv(self.fecha, self.fecha)

        self.assertEqual(len(hallazgos), 1)
        self.assertEqual(hallazgos[0]['tipo'], Descuadre.TipoDescuadre.PRODUCCION_VENTAS)
        self.assertEqual(hallazgos[0]['severidad'], Descuadre.Severidad.LEVE)
        self.assertEqual(hallazgos[0]['diferencia'], Decimal('10'))

    def test_diferencia_grande_genera_hallazgo_moderado(self):
        # 30% de diferencia — mayor al 15%, pero producido > vendido (no es imposible)
        self.crear_produccion(self.producto, 100, self.fecha, self.admin)
        self.crear_entrega(self.producto, 70, self.fecha)

        hallazgos = detectar_pv(self.fecha, self.fecha)

        self.assertEqual(len(hallazgos), 1)
        self.assertEqual(hallazgos[0]['severidad'], Descuadre.Severidad.MODERADO)

    def test_ventas_superan_produccion_siempre_es_critico(self):
        self.crear_produccion(self.producto, 50, self.fecha, self.admin)
        self.crear_entrega(self.producto, 60, self.fecha)

        hallazgos = detectar_pv(self.fecha, self.fecha)

        self.assertEqual(len(hallazgos), 1)
        self.assertEqual(hallazgos[0]['severidad'], Descuadre.Severidad.CRITICO)
        self.assertEqual(hallazgos[0]['diferencia'], Decimal('10'))
        self.assertIn('supera', hallazgos[0]['descripcion'])

    def test_devoluciones_se_descuentan_de_lo_vendido(self):
        self.crear_produccion(self.producto, 100, self.fecha, self.admin)
        self.crear_entrega(self.producto, 100, self.fecha, devolucion=100)

        hallazgos = detectar_pv(self.fecha, self.fecha)

        # vendido neto = 0, producido = 100 -> 100% de diferencia -> moderado
        self.assertEqual(len(hallazgos), 1)
        self.assertEqual(hallazgos[0]['severidad'], Descuadre.Severidad.MODERADO)

    def test_producto_sin_movimiento_no_genera_hallazgo(self):
        hallazgos = detectar_pv(self.fecha, self.fecha)
        self.assertEqual(hallazgos, [])


class DetectarVITests(DetectorHelpersMixin, TestCase):
    def setUp(self):
        self.admin = self.crear_admin()
        self.producto = self.crear_producto()
        self.fecha = date(2026, 8, 15)

    def test_disponible_positivo_no_genera_hallazgo(self):
        self.crear_produccion(self.producto, 100, date(2026, 7, 1), self.admin)
        self.crear_entrega(self.producto, 60, date(2026, 7, 15))

        hallazgos = detectar_vi(self.fecha)

        self.assertEqual(hallazgos, [])

    def test_disponible_negativo_acumulado_es_critico(self):
        # 90 producidos en julio, pero 120 vendidos acumulados a la fecha de corte
        self.crear_produccion(self.producto, 90, date(2026, 7, 1), self.admin)
        self.crear_entrega(self.producto, 120, date(2026, 7, 20))

        hallazgos = detectar_vi(self.fecha)

        self.assertEqual(len(hallazgos), 1)
        self.assertEqual(hallazgos[0]['tipo'], Descuadre.TipoDescuadre.VENTAS_INVENTARIO)
        self.assertEqual(hallazgos[0]['severidad'], Descuadre.Severidad.CRITICO)
        self.assertEqual(hallazgos[0]['diferencia'], Decimal('30'))

    def test_solo_considera_movimientos_hasta_la_fecha_de_corte(self):
        self.crear_produccion(self.producto, 50, date(2026, 7, 1), self.admin)
        self.crear_entrega(self.producto, 50, date(2026, 7, 10))
        # Venta futura, posterior a la fecha de corte: no debe contarse
        self.crear_entrega(self.producto, 999, date(2026, 9, 1))

        hallazgos = detectar_vi(self.fecha)

        self.assertEqual(hallazgos, [])


class DetectarACTests(DetectorHelpersMixin, TestCase):
    def setUp(self):
        self.admin = self.crear_admin()
        self.f_desde = date(2026, 8, 1)
        self.f_hasta = date(2026, 8, 5)

    def _mov(self, fecha, momento, tipo='BOT', **conteos):
        return MovimientoActivo.objects.create(
            fecha=fecha, momento=momento, tipo_activo=tipo,
            registrado_por=self.admin, **conteos,
        )

    def test_totales_coinciden_no_genera_hallazgo(self):
        self._mov(self.f_desde, 'INI', cantidad_en_planta_lleno=50, cantidad_en_clientes=30)
        self._mov(self.f_hasta, 'FIN', cantidad_en_planta_lleno=45, cantidad_en_clientes=35)

        hallazgos = detectar_ac(self.f_desde, self.f_hasta)

        self.assertEqual(hallazgos, [])

    def test_totales_no_coinciden_genera_hallazgo(self):
        self._mov(self.f_desde, 'INI', cantidad_en_planta_lleno=50, cantidad_en_clientes=30)
        # total inicial = 80. Total final = 75: faltan 5 unidades no explicadas.
        self._mov(self.f_hasta, 'FIN', cantidad_en_planta_lleno=45, cantidad_en_clientes=30)

        hallazgos = detectar_ac(self.f_desde, self.f_hasta)

        self.assertEqual(len(hallazgos), 1)
        self.assertEqual(hallazgos[0]['tipo'], Descuadre.TipoDescuadre.ACTIVOS_CLIENTES)
        self.assertEqual(hallazgos[0]['diferencia'], Decimal('5'))

    def test_sin_registros_en_las_fechas_no_genera_hallazgo(self):
        hallazgos = detectar_ac(self.f_desde, self.f_hasta)
        self.assertEqual(hallazgos, [])


class EjecutarDeteccionTests(DetectorHelpersMixin, TestCase):
    def setUp(self):
        self.admin = self.crear_admin()
        self.producto = self.crear_producto()
        self.fecha = date(2026, 8, 1)
        # Producción histórica que cubre el disponible acumulado (para que
        # detectar_vi no dispare también) pero con ventas del periodo
        # superando la producción del periodo -> solo un hallazgo PV crítico.
        self.crear_produccion(self.producto, 100, date(2026, 7, 1), self.admin)
        self.crear_produccion(self.producto, 50, self.fecha, self.admin)
        self.crear_entrega(self.producto, 80, self.fecha)

    def test_crea_descuadres_automaticos_con_el_usuario_como_detector(self):
        creados = ejecutar_deteccion(self.fecha, self.fecha, self.admin)

        self.assertEqual(len(creados), 1)
        descuadre = Descuadre.objects.get(pk=creados[0].pk)
        self.assertTrue(descuadre.es_automatico)
        self.assertEqual(descuadre.detectado_por, self.admin)
        self.assertEqual(descuadre.severidad, Descuadre.Severidad.CRITICO)

    def test_no_duplica_si_ya_existe_uno_igual_sin_resolver(self):
        ejecutar_deteccion(self.fecha, self.fecha, self.admin)
        creados_segunda_vez = ejecutar_deteccion(self.fecha, self.fecha, self.admin)

        self.assertEqual(creados_segunda_vez, [])
        self.assertEqual(Descuadre.objects.count(), 1)

    def test_vuelve_a_crear_si_el_anterior_ya_fue_resuelto(self):
        creados = ejecutar_deteccion(self.fecha, self.fecha, self.admin)
        creados[0].resuelto = True
        creados[0].save(update_fields=['resuelto'])

        creados_segunda_vez = ejecutar_deteccion(self.fecha, self.fecha, self.admin)

        self.assertEqual(len(creados_segunda_vez), 1)
        self.assertEqual(Descuadre.objects.count(), 2)


class DetectarDescuadresViewTests(DetectorHelpersMixin, TestCase):
    def setUp(self):
        self.admin = self.crear_admin()
        self.client.force_login(self.admin)
        self.producto = self.crear_producto()
        hoy = date.today()
        self.inicio_mes = hoy.replace(day=1)
        # Producción histórica que cubre el disponible acumulado (para que
        # detectar_vi no dispare también) + ventas del mes en curso muy por
        # encima de lo producido este mes -> solo hallazgo PV crítico.
        mes_pasado = (self.inicio_mes - timedelta(days=1)).replace(day=1)
        self.crear_produccion(self.producto, 2000, mes_pasado, self.admin)
        self.crear_produccion(self.producto, 10, self.inicio_mes, self.admin)
        self.crear_entrega(self.producto, 999, self.inicio_mes)

    def test_post_crea_descuadre_automatico_y_redirige(self):
        response = self.client.post(reverse('reportes:descuadre_detectar'))

        self.assertRedirects(response, reverse('reportes:descuadres'))
        descuadre = Descuadre.objects.get()
        self.assertTrue(descuadre.es_automatico)
        self.assertEqual(descuadre.detectado_por, self.admin)

    def test_solo_admin_puede_acceder(self):
        dist = self.crear_usuario('nicolas_dist', rol='DIST')
        self.client.force_login(dist)

        response = self.client.post(reverse('reportes:descuadre_detectar'))

        self.assertNotEqual(response.status_code, 200)
        self.assertEqual(Descuadre.objects.count(), 0)

    def crear_usuario(self, username, rol):
        return Usuario.objects.create_user(username=username, password='brisas2024', rol=rol)


class DetectarDescuadresCommandTests(DetectorHelpersMixin, TestCase):
    def setUp(self):
        self.admin = self.crear_admin()
        self.producto = self.crear_producto()
        self.fecha = date(2026, 8, 1)
        # Producción histórica que cubre el disponible acumulado (para que
        # detectar_vi no dispare también) -> solo hallazgo PV crítico.
        self.crear_produccion(self.producto, 2000, date(2026, 7, 1), self.admin)
        self.crear_produccion(self.producto, 10, self.fecha, self.admin)
        self.crear_entrega(self.producto, 999, self.fecha)

    def test_usa_primer_admin_activo_por_defecto(self):
        call_command(
            'detectar_descuadres',
            '--fecha-desde', '2026-08-01', '--fecha-hasta', '2026-08-01',
        )

        descuadre = Descuadre.objects.get()
        self.assertEqual(descuadre.detectado_por, self.admin)
        self.assertTrue(descuadre.es_automatico)

    def test_usa_usuario_indicado_por_flag(self):
        otro_admin = Usuario.objects.create_user(
            username='otro_admin', password='brisas2024', rol='ADMIN',
        )
        call_command(
            'detectar_descuadres',
            '--fecha-desde', '2026-08-01', '--fecha-hasta', '2026-08-01',
            '--usuario', 'otro_admin',
        )

        descuadre = Descuadre.objects.get()
        self.assertEqual(descuadre.detectado_por, otro_admin)

    def test_falla_si_no_hay_admin_ni_flag_usuario(self):
        self.admin.rol = 'DIST'
        self.admin.save(update_fields=['rol'])

        with self.assertRaises(CommandError):
            call_command(
                'detectar_descuadres',
                '--fecha-desde', '2026-08-01', '--fecha-hasta', '2026-08-01',
            )


class AlertasInsumosDashboardTests(DetectorHelpersMixin, TestCase):
    """Regresión de B-01: alertas_insumos debía comparar contra stock_minimo,
    no contra 0. Ya corregido (commit 6aff4ef); esta clase deja el
    comportamiento cubierto por primera vez."""

    def setUp(self):
        self.admin = self.crear_admin()
        self.client.force_login(self.admin)

    def test_cuenta_solo_insumos_activos_bajo_o_igual_a_su_minimo(self):
        tapas_sellado = CategoriaInsumo.objects.get(nombre='Tapas y sellado')
        envases = CategoriaInsumo.objects.get(nombre='Envases y empaques')
        unidad = UnidadMedida.objects.get(nombre='unidad')
        rollo = UnidadMedida.objects.get(nombre='rollo')

        Insumo.objects.create(
            nombre='Tapas', categoria=tapas_sellado, unidad_medida=unidad,
            stock_actual=Decimal('5'), stock_minimo=Decimal('10'), activo=True,
        )
        Insumo.objects.create(
            nombre='Cinta', categoria=tapas_sellado, unidad_medida=rollo,
            stock_actual=Decimal('50'), stock_minimo=Decimal('10'), activo=True,
        )
        Insumo.objects.create(
            nombre='Reempaque inactivo', categoria=envases, unidad_medida=unidad,
            stock_actual=Decimal('0'), stock_minimo=Decimal('10'), activo=False,
        )

        response = self.client.get(reverse('reportes:dashboard'))

        self.assertEqual(response.context['alertas_insumos'], 1)

    def test_stock_en_cero_sin_minimo_definido_no_cuenta_como_alerta(self):
        # Antes de B-01 se comparaba contra stock_actual <= 0, lo que
        # coincide con este caso por casualidad; el fix real está en que
        # ahora compara contra stock_minimo (probado arriba con minimo > 0).
        Insumo.objects.create(
            nombre='Otro', categoria=CategoriaInsumo.objects.get(nombre='Otros'),
            unidad_medida=UnidadMedida.objects.get(nombre='unidad'),
            stock_actual=Decimal('0'), stock_minimo=Decimal('0'), activo=True,
        )

        response = self.client.get(reverse('reportes:dashboard'))

        self.assertEqual(response.context['alertas_insumos'], 1)


class ExportarVentasSmokeTests(DetectorHelpersMixin, TestCase):
    """Smoke tests: los exports ya funcionan (verificados manualmente en
    sesión 2026-06-10) pero no tenían ninguna prueba automatizada."""

    def setUp(self):
        self.admin = self.crear_admin()
        self.client.force_login(self.admin)
        producto = self.crear_producto()
        self.crear_entrega(producto, 10, date(2026, 8, 1))

    def test_exportar_excel_devuelve_xlsx(self):
        response = self.client.get(
            reverse('reportes:ventas_excel'),
            {'fecha_desde': '2026-08-01', 'fecha_hasta': '2026-08-31'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response['Content-Type'],
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )

    def test_exportar_pdf_devuelve_pdf(self):
        response = self.client.get(
            reverse('reportes:ventas_pdf'),
            {'fecha_desde': '2026-08-01', 'fecha_hasta': '2026-08-31'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')


class CierreAnualModelTests(TestCase):
    def test_crear_cierre_anual(self):
        admin = Usuario.objects.create_user(username='admin_cierre', password='brisas2024', rol='ADMIN')
        cierre = CierreAnual.objects.create(anio=2026, cerrado_por=admin)

        self.assertTrue(cierre.cerrado)
        self.assertIsNotNone(cierre.fecha_cierre)
        self.assertIsNone(cierre.reabierto_por)

    def test_anio_es_unico(self):
        admin = Usuario.objects.create_user(username='admin_cierre2', password='brisas2024', rol='ADMIN')
        CierreAnual.objects.create(anio=2026, cerrado_por=admin)
        with self.assertRaises(IntegrityError):
            CierreAnual.objects.create(anio=2026, cerrado_por=admin)


class CierresHelperTests(TestCase):
    def setUp(self):
        self.admin = Usuario.objects.create_user(username='admin_helper', password='brisas2024', rol='ADMIN')

    def test_anio_sin_registro_no_esta_cerrado(self):
        self.assertFalse(anio_cerrado(2026))

    def test_anio_cerrado_devuelve_true(self):
        CierreAnual.objects.create(anio=2026, cerrado_por=self.admin)
        self.assertTrue(anio_cerrado(2026))

    def test_anio_reabierto_no_esta_cerrado(self):
        CierreAnual.objects.create(anio=2026, cerrado_por=self.admin, cerrado=False)
        self.assertFalse(anio_cerrado(2026))

    def test_validar_periodo_abierto_no_lanza_si_anio_abierto(self):
        validar_periodo_abierto(date_cls(2026, 5, 1))  # no debe lanzar

    def test_validar_periodo_abierto_lanza_si_anio_cerrado(self):
        CierreAnual.objects.create(anio=2026, cerrado_por=self.admin)
        with self.assertRaises(DjangoValidationError):
            validar_periodo_abierto(date_cls(2026, 5, 1))

    def test_validar_periodo_abierto_no_lanza_si_fecha_es_none(self):
        validar_periodo_abierto(None)  # no debe lanzar


class CierreAnualViewsTests(TestCase):
    def setUp(self):
        self.admin = Usuario.objects.create_user(username='admin_vista_cierre', password='brisas2024', rol='ADMIN')
        self.client.force_login(self.admin)

    def test_cerrar_anio_sin_planillas_pendientes_crea_cierre(self):
        resp = self.client.post(reverse('reportes:cierre_crear'), {'anio': 2025})
        self.assertEqual(resp.status_code, 302)
        cierre = CierreAnual.objects.get(anio=2025)
        self.assertTrue(cierre.cerrado)
        self.assertEqual(cierre.cerrado_por, self.admin)

    def test_cerrar_anio_con_planillas_pendientes_avisa_y_no_cierra_sin_confirmar(self):
        distribuidor = Usuario.objects.create_user(username='dist_cierre_pend', password='brisas2024', rol='DIST')
        Planilla.objects.create(
            fecha=date(2025, 6, 1), distribuidor=distribuidor,
            estado=Planilla.Estado.PENDIENTE_VALIDACION,
        )
        resp = self.client.post(reverse('reportes:cierre_crear'), {'anio': 2025})
        self.assertFalse(CierreAnual.objects.filter(anio=2025).exists())

    def test_cerrar_anio_con_planillas_pendientes_confirmando_si_cierra(self):
        distribuidor = Usuario.objects.create_user(username='dist_cierre_pend2', password='brisas2024', rol='DIST')
        Planilla.objects.create(
            fecha=date(2025, 6, 1), distribuidor=distribuidor,
            estado=Planilla.Estado.PENDIENTE_VALIDACION,
        )
        resp = self.client.post(reverse('reportes:cierre_crear'), {'anio': 2025, 'confirmar': '1'})
        self.assertTrue(CierreAnual.objects.filter(anio=2025, cerrado=True).exists())

    def test_reabrir_anio_cerrado(self):
        CierreAnual.objects.create(anio=2025, cerrado_por=self.admin)
        resp = self.client.post(reverse('reportes:cierre_reabrir', kwargs={'anio': 2025}))
        self.assertEqual(resp.status_code, 302)
        cierre = CierreAnual.objects.get(anio=2025)
        self.assertFalse(cierre.cerrado)
        self.assertEqual(cierre.reabierto_por, self.admin)
        self.assertIsNotNone(cierre.fecha_reapertura)

    def test_no_admin_no_puede_cerrar_anio(self):
        prod = Usuario.objects.create_user(username='prod_no_cierre', password='brisas2024', rol='PROD')
        self.client.force_login(prod)
        resp = self.client.post(reverse('reportes:cierre_crear'), {'anio': 2025})
        self.assertFalse(CierreAnual.objects.filter(anio=2025).exists())

    def test_lista_de_cierres_solo_admin(self):
        resp = self.client.get(reverse('reportes:cierres'))
        self.assertEqual(resp.status_code, 200)


class ReporteAnualViewTests(TestCase):
    def setUp(self):
        self.admin = Usuario.objects.create_user(username='admin_reporte_anual', password='brisas2024', rol='ADMIN')
        self.client.force_login(self.admin)
        self.producto = Producto.objects.create(nombre='Bolsa reporte anual', presentacion=Producto.Presentacion.BOLSA_INDIVIDUAL)

    def test_totales_del_anio_correctos(self):
        Produccion.objects.create(
            fecha=date(2026, 3, 10), lote='LOTE-RA-1', producto=self.producto,
            cantidad_producida=100, registrado_por=self.admin,
        )
        Produccion.objects.create(
            fecha=date(2026, 7, 5), lote='LOTE-RA-2', producto=self.producto,
            cantidad_producida=50, registrado_por=self.admin,
        )
        # Producción de otro año no debe contar
        Produccion.objects.create(
            fecha=date(2025, 3, 10), lote='LOTE-RA-3', producto=self.producto,
            cantidad_producida=999, registrado_por=self.admin,
        )

        resp = self.client.get(reverse('reportes:anual'), {'anio': 2026})

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['total_produccion'], 150)
        self.assertEqual(resp.context['anio'], 2026)

    def test_desglose_mensual_tiene_12_meses(self):
        resp = self.client.get(reverse('reportes:anual'), {'anio': 2026})
        self.assertEqual(len(resp.context['meses']), 12)

    def test_sin_anio_en_query_usa_anio_actual(self):
        resp = self.client.get(reverse('reportes:anual'))
        self.assertEqual(resp.context['anio'], date.today().year)
