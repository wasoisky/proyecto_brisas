from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from .models import ActivoRetornable, BajaActivo, MovimientoActivo

Usuario = get_user_model()


class ActivosTestMixin:
    def crear_usuario(self, username='cesar', rol='PROD'):
        return Usuario.objects.create_user(
            username=username, password='brisas2024', rol=rol,
            first_name='Test', last_name='User',
        )

    def crear_movimiento(self, **kwargs):
        defaults = dict(
            fecha='2026-08-30',
            momento=MovimientoActivo.Momento.INICIO_JORNADA,
            tipo_activo=ActivoRetornable.TipoActivo.BOTELLON,
            cantidad_en_planta_lleno=10,
            cantidad_en_planta_vacio=5,
            cantidad_en_clientes=20,
            cantidad_baja=2,
            registrado_por=self.usuario,
        )
        defaults.update(kwargs)
        return MovimientoActivo.objects.create(**defaults)


class MovimientoActivoModelTests(ActivosTestMixin, TestCase):
    def setUp(self):
        self.usuario = self.crear_usuario()

    def test_unique_together_fecha_momento_tipo_activo(self):
        self.crear_movimiento()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.crear_movimiento()

    def test_mismo_dia_distinto_momento_no_choca(self):
        self.crear_movimiento(momento=MovimientoActivo.Momento.INICIO_JORNADA)
        # No debe lanzar: momento distinto es una combinación distinta
        self.crear_movimiento(momento=MovimientoActivo.Momento.FIN_JORNADA)
        self.assertEqual(MovimientoActivo.objects.count(), 2)

    def test_total_suma_los_cuatro_estados(self):
        mov = self.crear_movimiento(
            cantidad_en_planta_lleno=10,
            cantidad_en_planta_vacio=5,
            cantidad_en_clientes=20,
            cantidad_baja=2,
        )
        self.assertEqual(mov.total, 37)


class BajaActivoModelTests(ActivosTestMixin, TestCase):
    def setUp(self):
        self.usuario = self.crear_usuario()
        self.movimiento = self.crear_movimiento()

    def test_motivo_por_defecto_es_rotura(self):
        baja = BajaActivo.objects.create(
            movimiento=self.movimiento,
            cantidad=1,
            registrado_por=self.usuario,
        )
        self.assertEqual(baja.motivo, BajaActivo.Motivo.ROTURA)

    def test_str_incluye_tipo_cantidad_y_motivo(self):
        baja = BajaActivo.objects.create(
            movimiento=self.movimiento,
            cantidad=3,
            motivo=BajaActivo.Motivo.PERDIDA,
            registrado_por=self.usuario,
        )
        texto = str(baja)
        self.assertIn('3', texto)
        self.assertIn('Pérdida', texto)

    def test_se_borra_en_cascada_con_el_movimiento(self):
        BajaActivo.objects.create(
            movimiento=self.movimiento, cantidad=1, registrado_por=self.usuario,
        )
        self.movimiento.delete()
        self.assertEqual(BajaActivo.objects.count(), 0)


class BajaActivoFormTests(ActivosTestMixin, TestCase):
    def setUp(self):
        self.usuario = self.crear_usuario()
        self.movimiento = self.crear_movimiento()

    def test_form_valido_con_datos_minimos(self):
        from .forms import BajaActivoForm
        form = BajaActivoForm(data={
            'cantidad': 2,
            'motivo': BajaActivo.Motivo.ROTURA,
            'descripcion': '',
        })
        self.assertTrue(form.is_valid(), form.errors)

    def test_form_rechaza_cantidad_cero(self):
        from .forms import BajaActivoForm
        form = BajaActivoForm(data={
            'cantidad': 0,
            'motivo': BajaActivo.Motivo.ROTURA,
            'descripcion': '',
        })
        self.assertFalse(form.is_valid())


class BajaActivoViewTests(ActivosTestMixin, TestCase):
    def setUp(self):
        self.usuario = self.crear_usuario()
        self.movimiento = self.crear_movimiento()
        self.client.force_login(self.usuario)

    def test_crear_baja_registra_registrado_por_y_redirige_al_detalle(self):
        url = reverse('activos:baja_create', args=[self.movimiento.pk])
        response = self.client.post(url, {
            'cantidad': 1,
            'motivo': BajaActivo.Motivo.ROBO,
            'descripcion': 'faltante en bodega',
        })
        self.assertRedirects(
            response, reverse('activos:movimiento_detail', args=[self.movimiento.pk])
        )
        baja = BajaActivo.objects.get()
        self.assertEqual(baja.registrado_por, self.usuario)
        self.assertEqual(baja.movimiento, self.movimiento)

    def test_detalle_de_movimiento_lista_sus_bajas(self):
        BajaActivo.objects.create(
            movimiento=self.movimiento, cantidad=1,
            motivo=BajaActivo.Motivo.DETERIORO, registrado_por=self.usuario,
        )
        url = reverse('activos:movimiento_detail', args=[self.movimiento.pk])
        response = self.client.get(url)
        self.assertContains(response, 'Deterioro')

    def test_dist_no_puede_registrar_bajas(self):
        dist = self.crear_usuario(username='nicolas', rol='DIST')
        self.client.force_login(dist)
        url = reverse('activos:baja_create', args=[self.movimiento.pk])
        response = self.client.post(url, {
            'cantidad': 1, 'motivo': BajaActivo.Motivo.ROTURA, 'descripcion': '',
        })
        self.assertRedirects(response, '/distribucion/ruta/')
        self.assertEqual(BajaActivo.objects.count(), 0)
