from datetime import date
from unittest import mock

from django.contrib import messages
from django.contrib.messages.storage.base import Message
from django.template.loader import render_to_string
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings

from activos.forms import MovimientoActivoForm
from distribucion.forms import PlanillaForm
from produccion.forms import CompraInsumoForm, ProduccionForm, RegaliaForm
from reportes.forms import DescuadreForm, FiltroVentasForm


class FechaInputISOTests(TestCase):
    """Un <input type="date"> solo entiende yyyy-mm-dd: con el formato regional
    es-co (d/m/Y) el navegador ignora el value y el campo aparece vacío."""

    FECHA = date(2026, 9, 27)

    def _assert_value_iso(self, form, campo):
        html = str(form[campo])
        self.assertIn('type="date"', html)
        self.assertIn('value="2026-09-27"', html, html)

    def test_formularios_modelo_renderizan_fecha_en_iso(self):
        for form_class in (
            ProduccionForm, CompraInsumoForm, RegaliaForm,
            MovimientoActivoForm, PlanillaForm, DescuadreForm,
        ):
            with self.subTest(form=form_class.__name__):
                form = form_class(initial={'fecha': self.FECHA})
                self._assert_value_iso(form, 'fecha')

    def test_filtro_ventas_renderiza_fechas_en_iso(self):
        form = FiltroVentasForm(
            [], initial={'fecha_desde': self.FECHA, 'fecha_hasta': self.FECHA},
        )
        self._assert_value_iso(form, 'fecha_desde')
        self._assert_value_iso(form, 'fecha_hasta')

    def test_fecha_enviada_en_iso_sigue_siendo_valida(self):
        form = FiltroVentasForm([], data={'fecha_desde': '2026-09-27'})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['fecha_desde'], self.FECHA)


class MensajesErrorBootstrapTests(SimpleTestCase):
    """Django etiqueta messages.error como 'error', pero Bootstrap solo define
    alert-danger."""

    def test_etiqueta_de_error_es_danger(self):
        self.assertEqual(Message(messages.ERROR, 'x').level_tag, 'danger')

    def test_base_renderiza_error_con_alert_danger_e_icono_rojo(self):
        msg = Message(messages.ERROR, 'Stock insuficiente')
        request = RequestFactory().get('/')
        request.user = mock.Mock(is_authenticated=False)
        html = render_to_string('base.html', {'messages': [msg]}, request=request)
        self.assertIn('alert-danger', html)
        self.assertIn('bi-x-circle', html)
        self.assertNotIn('alert-error', html)
