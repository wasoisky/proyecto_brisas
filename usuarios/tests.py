from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Usuario
from .mixins import TODOS, ADMIN_PROD, SOLO_ADMIN, ADMIN_DIST, RolRequiredMixin
from .forms import AdminPasswordResetForm


class UsuarioTestMixin:
    """Helpers compartidos por los TestCase del módulo."""

    def crear_admin(self, username='maximino', password='brisas2024'):
        return Usuario.objects.create_user(
            username=username,
            password=password,
            rol='ADMIN',
            first_name='Admin',
            last_name='Test',
        )

    def crear_usuario(self, username, rol, password='brisas2024'):
        return Usuario.objects.create_user(
            username=username,
            password=password,
            rol=rol,
            first_name='Test',
            last_name='User',
        )


class MixinsTests(TestCase):
    def test_role_constants_son_tuplas(self):
        self.assertIsInstance(TODOS, tuple)
        self.assertIsInstance(ADMIN_PROD, tuple)
        self.assertIsInstance(SOLO_ADMIN, tuple)
        self.assertIsInstance(ADMIN_DIST, tuple)

    def test_roles_permitidos_default_es_tupla(self):
        self.assertIsInstance(RolRequiredMixin.roles_permitidos, tuple)


_VALIDATORS_MINIMOS = [
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {'min_length': 8},
    },
]


class AdminPasswordResetFormTests(TestCase):
    @override_settings(AUTH_PASSWORD_VALIDATORS=_VALIDATORS_MINIMOS)
    def test_contrasena_corta_es_rechazada(self):
        form = AdminPasswordResetForm(data={'password1': '123', 'password2': '123'})
        self.assertFalse(form.is_valid())
        self.assertIn('password1', form.errors)

    @override_settings(AUTH_PASSWORD_VALIDATORS=_VALIDATORS_MINIMOS)
    def test_contrasena_fuerte_es_aceptada(self):
        form = AdminPasswordResetForm(
            data={'password1': 'Brisas2024!', 'password2': 'Brisas2024!'}
        )
        self.assertTrue(form.is_valid())

    def test_contrasenas_distintas_son_rechazadas(self):
        form = AdminPasswordResetForm(
            data={'password1': 'Brisas2024!', 'password2': 'OtroValor2024!'}
        )
        self.assertFalse(form.is_valid())
