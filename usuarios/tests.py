import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from .admin import UsuarioAdmin
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

    @override_settings(AUTH_PASSWORD_VALIDATORS=[
        {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    ])
    def test_contrasena_similar_al_username_es_rechazada(self):
        usuario = Usuario(username='nicolas', first_name='Nicolas', last_name='Diaz')
        form = AdminPasswordResetForm(
            data={'password1': 'nicolas123', 'password2': 'nicolas123'},
            usuario=usuario,
        )
        self.assertFalse(form.is_valid())
        self.assertIn('password1', form.errors)


class BackupViewsTests(UsuarioTestMixin, TestCase):
    def setUp(self):
        self.superuser = Usuario.objects.create_superuser(
            username='superadmin_web', password='brisas2024',
        )
        self.admin_negocio = self.crear_admin(username='maximino2')

    def test_lista_rechaza_a_admin_de_negocio_no_superusuario(self):
        self.client.force_login(self.admin_negocio)
        response = self.client.get(reverse('usuarios:backups'))
        self.assertNotEqual(response.status_code, 200)

    def test_lista_permite_a_superusuario(self):
        self.client.force_login(self.superuser)
        response = self.client.get(reverse('usuarios:backups'))
        self.assertEqual(response.status_code, 200)

    def test_lista_muestra_los_backups_existentes(self):
        self.client.force_login(self.superuser)
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / 'backups').mkdir()
            (Path(tmp) / 'backups' / 'brisas_pacande_20260101_000000.dump').write_bytes(b'x' * 100)
            with override_settings(BASE_DIR=Path(tmp)):
                response = self.client.get(reverse('usuarios:backups'))
            self.assertContains(response, 'brisas_pacande_20260101_000000.dump')

    @patch('usuarios.views.generar_backup')
    def test_generar_llama_a_generar_backup_y_redirige(self, mock_generar):
        mock_generar.return_value = Path('brisas_pacande_20260101_000000.dump')
        self.client.force_login(self.superuser)
        response = self.client.post(reverse('usuarios:backups_generar'))
        self.assertTrue(mock_generar.called)
        self.assertRedirects(response, reverse('usuarios:backups'))

    @patch('usuarios.views.generar_backup')
    def test_generar_con_pg_dump_fallido_no_crashea(self, mock_generar):
        from usuarios.backup import BackupError
        mock_generar.side_effect = BackupError('pg_dump falló: conexion rechazada')
        self.client.force_login(self.superuser)
        response = self.client.post(reverse('usuarios:backups_generar'))
        self.assertRedirects(response, reverse('usuarios:backups'))

    def test_generar_rechaza_a_no_superusuario(self):
        self.client.force_login(self.admin_negocio)
        response = self.client.post(reverse('usuarios:backups_generar'))
        self.assertNotEqual(response.status_code, 200)

    def test_descargar_devuelve_el_archivo(self):
        self.client.force_login(self.superuser)
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / 'backups').mkdir()
            (Path(tmp) / 'backups' / 'brisas_pacande_20260101_000000.dump').write_bytes(b'contenido-dump')
            with override_settings(BASE_DIR=Path(tmp)):
                response = self.client.get(
                    reverse('usuarios:backups_descargar', args=['brisas_pacande_20260101_000000.dump'])
                )
                contenido = b''.join(response.streaming_content)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(contenido, b'contenido-dump')

    def test_descargar_con_nombre_no_listado_devuelve_404(self):
        self.client.force_login(self.superuser)
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / 'backups').mkdir()
            (Path(tmp) / 'backups' / 'brisas_pacande_20260101_000000.dump').write_bytes(b'x')
            with override_settings(BASE_DIR=Path(tmp)):
                response = self.client.get(
                    reverse('usuarios:backups_descargar', args=['..%2F..%2Fsettings.py'])
                )
            self.assertEqual(response.status_code, 404)

    def test_descargar_rechaza_a_no_superusuario(self):
        self.client.force_login(self.admin_negocio)
        response = self.client.get(
            reverse('usuarios:backups_descargar', args=['brisas_pacande_20260101_000000.dump'])
        )
        self.assertNotEqual(response.status_code, 200)


class GenerarBackupTests(TestCase):
    @patch('usuarios.backup.subprocess.run')
    def test_pg_dump_no_encontrado_lanza_backuperror_claro(self, mock_run):
        from usuarios.backup import BackupError, generar_backup

        mock_run.side_effect = FileNotFoundError()
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(BackupError) as ctx:
                generar_backup(destino=tmp)
        self.assertIn('pg_dump', str(ctx.exception))
        self.assertIn('PATH', str(ctx.exception))


class BackupBdCommandTests(TestCase):
    @patch('usuarios.backup.subprocess.run')
    def test_genera_dump_llamando_pg_dump(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stderr='')
        with tempfile.TemporaryDirectory() as tmp:
            call_command('backup_bd', destino=tmp)
            self.assertTrue(mock_run.called)
            comando = mock_run.call_args.args[0]
            self.assertEqual(comando[0], 'pg_dump')
            archivos = list(Path(tmp).iterdir())
            self.assertEqual(len(archivos), 0)  # pg_dump está mockeado, no crea el archivo real

    @patch('usuarios.backup.subprocess.run')
    def test_pg_dump_con_error_lanza_commanderror(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stderr='conexion rechazada')
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(CommandError):
                call_command('backup_bd', destino=tmp)

    @override_settings(DATABASES={
        'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': 'x'},
    })
    def test_motor_no_postgresql_lanza_commanderror(self):
        with self.assertRaises(CommandError):
            call_command('backup_bd')


class UsuarioAdminTests(UsuarioTestMixin, TestCase):
    def setUp(self):
        self.site = AdminSite()
        self.model_admin = UsuarioAdmin(Usuario, self.site)
        self.factory = RequestFactory()

    def test_rol_es_readonly_al_editar_su_propio_usuario(self):
        admin = self.crear_admin()
        request = self.factory.get(f'/admin/usuarios/usuario/{admin.pk}/change/')
        request.user = admin
        readonly = self.model_admin.get_readonly_fields(request, obj=admin)
        self.assertIn('rol', readonly)

    def test_rol_no_es_readonly_al_editar_otro_usuario(self):
        admin = self.crear_admin()
        otro = self.crear_usuario('nicolas', rol='PROD')
        request = self.factory.get(f'/admin/usuarios/usuario/{otro.pk}/change/')
        request.user = admin
        readonly = self.model_admin.get_readonly_fields(request, obj=otro)
        self.assertNotIn('rol', readonly)

    def test_rol_no_es_readonly_al_crear_usuario_nuevo(self):
        admin = self.crear_admin()
        request = self.factory.get('/admin/usuarios/usuario/add/')
        request.user = admin
        readonly = self.model_admin.get_readonly_fields(request, obj=None)
        self.assertNotIn('rol', readonly)

    def _staff_con_permiso(self, *codenames):
        staff = Usuario.objects.create_user(
            username='staff', password='brisas2024', rol='ADMIN',
            first_name='Staff', last_name='User', is_staff=True,
        )
        ct = ContentType.objects.get_for_model(Usuario)
        for codename in codenames:
            staff.user_permissions.add(Permission.objects.get(content_type=ct, codename=codename))
        return staff

    def test_staff_no_superusuario_no_puede_editar_a_un_superusuario(self):
        staff = self._staff_con_permiso('change_usuario')
        super_user = Usuario.objects.create_superuser(username='superadmin3', password='brisas2024')
        request = self.factory.get(f'/admin/usuarios/usuario/{super_user.pk}/change/')
        request.user = staff
        self.assertFalse(self.model_admin.has_change_permission(request, obj=super_user))

    def test_staff_no_superusuario_puede_editar_a_otro_no_superusuario(self):
        staff = self._staff_con_permiso('change_usuario')
        otro = self.crear_usuario('nicolas', rol='PROD')
        request = self.factory.get(f'/admin/usuarios/usuario/{otro.pk}/change/')
        request.user = staff
        self.assertTrue(self.model_admin.has_change_permission(request, obj=otro))

    def test_staff_no_superusuario_no_puede_borrar_a_un_superusuario(self):
        staff = self._staff_con_permiso('delete_usuario')
        super_user = Usuario.objects.create_superuser(username='superadmin4', password='brisas2024')
        request = self.factory.get(f'/admin/usuarios/usuario/{super_user.pk}/delete/')
        request.user = staff
        self.assertFalse(self.model_admin.has_delete_permission(request, obj=super_user))

    def test_superusuario_si_puede_editar_a_otro_superusuario(self):
        super_admin = Usuario.objects.create_superuser(username='superadmin5', password='brisas2024')
        otro_super = Usuario.objects.create_superuser(username='superadmin6', password='brisas2024')
        request = self.factory.get(f'/admin/usuarios/usuario/{otro_super.pk}/change/')
        request.user = super_admin
        self.assertTrue(self.model_admin.has_change_permission(request, obj=otro_super))


class UsuarioUpdateViewTests(UsuarioTestMixin, TestCase):
    def setUp(self):
        self.admin = self.crear_admin()
        self.client.force_login(self.admin)

    def test_admin_no_puede_cambiar_su_propio_rol(self):
        response = self.client.post(
            reverse('usuarios:editar', args=[self.admin.pk]),
            data={
                'first_name': 'Admin',
                'last_name': 'Test',
                'email': '',
                'telefono': '',
                'rol': 'PROD',
                'is_active': True,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.rol, 'ADMIN')

    def test_admin_puede_cambiar_rol_de_otro_usuario(self):
        otro = self.crear_usuario('nicolas', rol='PROD')
        response = self.client.post(
            reverse('usuarios:editar', args=[otro.pk]),
            data={
                'first_name': 'Test',
                'last_name': 'User',
                'email': '',
                'telefono': '',
                'rol': 'DIST',
                'is_active': True,
            },
        )
        self.assertRedirects(response, reverse('usuarios:lista'))
        otro.refresh_from_db()
        self.assertEqual(otro.rol, 'DIST')

    def test_get_editar_superusuario_retorna_404(self):
        super_user = Usuario.objects.create_superuser(
            username='superadmin',
            password='brisas2024',
        )
        response = self.client.get(reverse('usuarios:editar', args=[super_user.pk]))
        self.assertEqual(response.status_code, 404)

    def test_post_editar_superusuario_retorna_404(self):
        super_user = Usuario.objects.create_superuser(
            username='superadmin2',
            password='brisas2024',
        )
        response = self.client.post(
            reverse('usuarios:editar', args=[super_user.pk]),
            data={
                'first_name': 'Hackeado',
                'last_name': 'Test',
                'email': '',
                'telefono': '',
                'rol': 'ADMIN',
                'is_active': True,
            },
        )
        self.assertEqual(response.status_code, 404)

    def test_auto_edicion_con_rol_y_activo_invalidos_muestra_ambos_errores(self):
        response = self.client.post(
            reverse('usuarios:editar', args=[self.admin.pk]),
            data={
                'first_name': 'Admin',
                'last_name': 'Test',
                'email': '',
                'telefono': '',
                'rol': 'PROD',
                'is_active': False,
            },
        )
        self.assertEqual(response.status_code, 200)
        form = response.context['form']
        self.assertIn('rol', form.errors)
        self.assertIn('is_active', form.errors)
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.rol, 'ADMIN')
        self.assertTrue(self.admin.is_active)

    def test_get_editar_usuario_normal_renderiza_formulario(self):
        otro = self.crear_usuario('cesar', rol='PROD')
        response = self.client.get(reverse('usuarios:editar', args=[otro.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'cesar')
