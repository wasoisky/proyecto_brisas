"""Bitácora de auditoría de operaciones (RS-03): quién creó, modificó o eliminó qué y cuándo.

Se registra automáticamente por señales en todos los modelos de negocio de los cinco módulos.
"""
from datetime import date
from decimal import Decimal

from django.contrib import admin
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from distribucion.models import Cliente, Planilla, PrecioPorCategoria
from produccion.models import Producto

from .admin import RegistroAuditoriaAdmin
from .models import RegistroAcceso, RegistroAuditoria, Usuario


def auditoria(**filtros):
    return RegistroAuditoria.objects.filter(**filtros)


class AuditoriaSenalesTests(TestCase):
    def test_crear_registra_la_operacion_y_el_registro_afectado(self):
        p = Producto.objects.create(nombre='Botellón 20L', presentacion='BOT')
        r = auditoria(modelo='produccion.Producto', accion='CRE').get()
        self.assertEqual(r.objeto_id, str(p.pk))
        self.assertIn('Botellón 20L', r.descripcion)
        self.assertIsNone(r.usuario)                 # fuera de una petición web: acción del sistema
        self.assertEqual(r.cambios['nombre'], 'Botellón 20L')

    def test_modificar_guarda_valor_anterior_y_posterior(self):
        p = Producto.objects.create(nombre='Viejo', presentacion='BOT')
        p.nombre = 'Nuevo'
        p.save()
        r = auditoria(modelo='produccion.Producto', accion='MOD').get()
        self.assertEqual(r.cambios, {'nombre': ['Viejo', 'Nuevo']})

    def test_guardar_sin_cambios_no_genera_registro(self):
        p = Producto.objects.create(nombre='Igual', presentacion='BOT')
        antes = RegistroAuditoria.objects.count()
        p.save()
        self.assertEqual(RegistroAuditoria.objects.count(), antes)

    def test_eliminar_conserva_la_descripcion_del_registro(self):
        p = Producto.objects.create(nombre='Para borrar', presentacion='BOT')
        pk = p.pk
        p.delete()
        r = auditoria(modelo='produccion.Producto', accion='ELI').get()
        self.assertEqual(r.objeto_id, str(pk))
        self.assertIn('Para borrar', r.descripcion)

    def test_con_update_fields_solo_se_compara_lo_que_se_guarda(self):
        p = Producto.objects.create(nombre='A', presentacion='BOT')
        p.nombre = 'B'
        p.activo = False
        p.save(update_fields=['nombre'])
        r = auditoria(modelo='produccion.Producto', accion='MOD').get()
        self.assertEqual(list(r.cambios), ['nombre'])

    def test_la_bitacora_de_accesos_y_la_propia_auditoria_no_se_auditan(self):
        RegistroAcceso.objects.create(username_intento='x', accion='FALLO')
        self.assertFalse(auditoria(modelo='usuarios.RegistroAcceso').exists())
        self.assertFalse(auditoria(modelo='usuarios.RegistroAuditoria').exists())

    def test_el_cambio_de_contrasena_no_expone_el_hash(self):
        u = Usuario.objects.create_user(username='ana', password='uno', rol='PROD')
        u.set_password('dos')
        u.save()
        r = auditoria(modelo='usuarios.Usuario', accion='MOD').get()
        self.assertEqual(r.cambios['password'], ['[oculta]', '[modificada]'])
        self.assertNotIn('pbkdf2', str(r.cambios))
        # y la creación tampoco guarda el hash
        c = auditoria(modelo='usuarios.Usuario', accion='CRE').get()
        self.assertNotIn('pbkdf2', str(c.cambios))

    def test_actualizar_solo_last_login_no_hace_ruido(self):
        u = Usuario.objects.create_user(username='ana', password='uno', rol='PROD')
        antes = RegistroAuditoria.objects.count()
        u.last_login = timezone.now()
        u.save(update_fields=['last_login'])
        self.assertEqual(RegistroAuditoria.objects.count(), antes)


class AuditoriaPeticionTests(TestCase):
    def setUp(self):
        self.admin = Usuario.objects.create_user(username='edwin', password='x', rol='ADMIN')
        self.dist = Usuario.objects.create_user(username='nico', password='x', rol='DIST')

    def test_una_accion_web_queda_atribuida_al_usuario_y_su_ip(self):
        p = Producto.objects.create(nombre='Hielo', presentacion='BOT')
        self.client.force_login(self.admin)
        self.client.post(reverse('produccion:producto_toggle', args=[p.pk]))
        r = auditoria(modelo='produccion.Producto', accion='MOD').get()
        self.assertEqual(r.usuario, self.admin)
        self.assertEqual(r.usuario_nombre, 'edwin')
        self.assertEqual(r.cambios['activo'], [True, False])
        self.assertEqual(r.ip, '127.0.0.1')

    def test_una_operacion_de_la_api_queda_atribuida_al_distribuidor(self):
        prod = Producto.objects.create(nombre='Botellón', presentacion='BOT')
        PrecioPorCategoria.objects.create(categoria='REG', producto=prod, precio=Decimal('3000'))
        cli = Cliente.objects.create(nombre='Tienda', categoria='REG')
        pl = Planilla.objects.create(distribuidor=self.dist, fecha=date.today())
        api = APIClient()
        api.force_authenticate(self.dist)
        resp = api.post(reverse('distribucion:api_entrega_create'), {
            'planilla': pl.pk, 'cliente': cli.pk, 'producto': prod.pk, 'cantidad': 2,
            'precio_unitario': '3000', 'modalidad_pago': 'CRE', 'devolucion': 0,
        })
        self.assertEqual(resp.status_code, 201)
        e = auditoria(modelo='distribucion.Entrega', accion='CRE').get()
        self.assertEqual(e.usuario, self.dist)
        # el crédito que se genera automáticamente también queda registrado
        self.assertTrue(auditoria(modelo='distribucion.Credito', accion='CRE', usuario=self.dist).exists())

    def test_iniciar_sesion_no_genera_registros_de_auditoria(self):
        antes = RegistroAuditoria.objects.count()
        resp = self.client.post(reverse('login'), {'username': 'edwin', 'password': 'x'})
        self.assertEqual(resp.status_code, 302)          # inicio de sesión correcto
        self.assertEqual(RegistroAuditoria.objects.count(), antes)


class AuditoriaVistaTests(TestCase):
    def setUp(self):
        self.admin = Usuario.objects.create_user(username='edwin', password='x', rol='ADMIN')
        self.prod = Usuario.objects.create_user(username='wil', password='x', rol='PROD')
        self.dist = Usuario.objects.create_user(username='nico', password='x', rol='DIST')
        self.p = Producto.objects.create(nombre='Hielo', presentacion='BOT')
        self.client.force_login(self.admin)
        self.client.post(reverse('produccion:producto_toggle', args=[self.p.pk]))
        self.url = reverse('usuarios:auditoria')

    def test_el_admin_ve_la_bitacora(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Hielo')
        self.assertContains(resp, 'edwin')

    def test_filtra_por_operacion_modelo_y_usuario(self):
        self.assertEqual(
            {r.accion for r in self.client.get(self.url, {'accion': 'MOD'}).context['registros']}, {'MOD'})
        self.assertEqual(
            {r.modelo for r in self.client.get(self.url, {'modelo': 'produccion.Producto'}).context['registros']},
            {'produccion.Producto'})
        self.assertEqual(
            {r.usuario_nombre for r in self.client.get(self.url, {'usuario': 'edw'}).context['registros']},
            {'edwin'})

    def test_produccion_y_distribucion_no_acceden(self):
        for u in (self.prod, self.dist):
            self.client.force_login(u)
            self.assertNotEqual(self.client.get(self.url).status_code, 200)

    def test_el_registro_es_de_solo_lectura_en_el_panel_de_administracion(self):
        ma = RegistroAuditoriaAdmin(RegistroAuditoria, admin.site)
        self.assertFalse(ma.has_add_permission(None))
        self.assertFalse(ma.has_change_permission(None))
        self.assertFalse(ma.has_delete_permission(None))

    def test_los_cambios_se_muestran_en_lenguaje_legible(self):
        r = auditoria(modelo='produccion.Producto', accion='MOD').get()
        self.assertEqual(r.get_modelo_display(), 'Producto')
        campo, antes, despues = r.cambios_legibles[0]
        self.assertEqual((campo, antes, despues), ('Activo', 'True', 'False'))
