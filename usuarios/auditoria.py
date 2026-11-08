"""Auditoría de operaciones (RS-03): señales que registran crear, modificar y eliminar.

Cubre todos los modelos de las cinco apps del sistema (salvo las bitácoras mismas). Los
valores anteriores de una modificación se leen de la base justo antes de guardar.
Limitación conocida: las actualizaciones masivas con ``QuerySet.update()`` no disparan señales
(p. ej. el descuento de stock de insumos, que es consecuencia de registrar la producción o la
compra, que sí quedan registradas).
"""
import contextvars
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from django.db.models.signals import post_delete, post_save, pre_delete, pre_save

from .ip import obtener_ip_cliente

APPS_AUDITADAS = {'usuarios', 'produccion', 'activos', 'distribucion', 'reportes'}
MODELOS_EXCLUIDOS = {'usuarios.registroacceso', 'usuarios.registroauditoria'}
# Campos que cambian solos (ruido) y no son una operación de la persona.
CAMPOS_RUIDO = {'last_login', 'actualizado_en'}
CAMPOS_SECRETOS = {'password'}

_request_actual = contextvars.ContextVar('auditoria_request', default=None)


def fijar_request(request):
    """Guarda la petición en curso para atribuir la operación a su usuario e IP."""
    return _request_actual.set(request)


def soltar_request(token):
    _request_actual.reset(token)


def _auditable(sender):
    meta = sender._meta
    # Los modelos «históricos» de las migraciones de datos (módulo __fake__) no se auditan:
    # corren antes de que exista la tabla de la bitácora y no son operaciones de una persona.
    if getattr(sender, '__module__', '') == '__fake__':
        return False
    return (
        meta.app_label in APPS_AUDITADAS
        and meta.label_lower not in MODELOS_EXCLUIDOS
        and not meta.auto_created
    )


def _valor(v):
    if v is None or isinstance(v, (bool, int, float)):
        return v
    if isinstance(v, (Decimal, UUID)):
        return str(v)
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    texto = str(v)
    return texto if len(texto) <= 200 else texto[:197] + '...'


def _campos(instance, solo=None):
    """{atributo: valor} de los campos concretos (sin ruido; la contraseña se oculta)."""
    resultado = {}
    for f in instance._meta.concrete_fields:
        if f.attname in CAMPOS_RUIDO:
            continue
        if solo is not None and f.name not in solo and f.attname not in solo:
            continue
        if f.attname in CAMPOS_SECRETOS:
            resultado[f.attname] = '[oculta]'
        else:
            resultado[f.attname] = _valor(getattr(instance, f.attname))
    return resultado


def _usuario_e_ip():
    request = _request_actual.get()
    if request is None:
        return None, None
    usuario = getattr(request, 'user', None)
    if usuario is not None and not getattr(usuario, 'is_authenticated', False):
        usuario = None
    try:
        ip = obtener_ip_cliente(request)
    except Exception:
        ip = None
    return usuario, ip


def _descripcion(instance):
    try:
        return str(instance)[:255]
    except Exception:
        return f'{instance._meta.verbose_name} #{instance.pk}'


def registrar(accion, instance, cambios, descripcion=None):
    from .models import RegistroAuditoria
    usuario, ip = _usuario_e_ip()
    RegistroAuditoria.objects.create(
        usuario=usuario,
        usuario_nombre=usuario.get_username() if usuario else '',
        accion=accion,
        modelo=instance._meta.label,
        objeto_id=str(instance.pk),
        descripcion=descripcion if descripcion is not None else _descripcion(instance),
        cambios=cambios,
        ip=ip,
    )


def _antes_de_guardar(sender, instance, raw=False, **kwargs):
    if raw or not _auditable(sender) or instance.pk is None:
        return
    instance._auditoria_antes = sender._base_manager.filter(pk=instance.pk).values().first()


def _despues_de_guardar(sender, instance, created, raw=False, update_fields=None, **kwargs):
    if raw or not _auditable(sender):
        return
    from .models import RegistroAuditoria
    if created:
        registrar(RegistroAuditoria.Accion.CREAR, instance, _campos(instance))
        return
    antes = getattr(instance, '_auditoria_antes', None)
    if not antes:
        return
    ahora = _campos(instance, solo=set(update_fields) if update_fields else None)
    cambios = {}
    for campo, nuevo in ahora.items():
        if campo in CAMPOS_SECRETOS:
            if antes.get(campo) != getattr(instance, campo):
                cambios[campo] = ['[oculta]', '[modificada]']
            continue
        previo = _valor(antes.get(campo))
        if previo != nuevo:
            cambios[campo] = [previo, nuevo]
    instance._auditoria_antes = None
    if cambios:
        registrar(RegistroAuditoria.Accion.MODIFICAR, instance, cambios)


def _antes_de_borrar(sender, instance, **kwargs):
    if _auditable(sender):
        instance._auditoria_descripcion = _descripcion(instance)


def _despues_de_borrar(sender, instance, **kwargs):
    if not _auditable(sender):
        return
    from .models import RegistroAuditoria
    registrar(
        RegistroAuditoria.Accion.ELIMINAR, instance, _campos(instance),
        descripcion=getattr(instance, '_auditoria_descripcion', None),
    )


def conectar():
    """Conecta las señales (se llama una vez desde UsuariosConfig.ready)."""
    pre_save.connect(_antes_de_guardar, dispatch_uid='auditoria_pre_save')
    post_save.connect(_despues_de_guardar, dispatch_uid='auditoria_post_save')
    pre_delete.connect(_antes_de_borrar, dispatch_uid='auditoria_pre_delete')
    post_delete.connect(_despues_de_borrar, dispatch_uid='auditoria_post_delete')
