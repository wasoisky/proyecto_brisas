from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Usuario
from .mixins import TODOS, ADMIN_PROD, SOLO_ADMIN, ADMIN_DIST, RolRequiredMixin


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
