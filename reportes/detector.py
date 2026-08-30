"""Detección automática de descuadres (HU-13).

Compara producción, ventas y disponible acumulado por producto, y el conteo
de activos retornables entre dos fechas, para proponer registros de
``Descuadre`` sin intervención manual. Ver reportes/MODULO_REPORTES.md para
la justificación de los umbrales y del alcance de cada tipo.
"""
from decimal import Decimal

from django.db.models import F, Sum

from activos.models import ActivoRetornable, MovimientoActivo
from distribucion.models import Entrega
from produccion.models import Producto, Produccion
from .models import Descuadre

UMBRAL_LEVE = Decimal('0.05')
UMBRAL_MODERADO = Decimal('0.15')


def _vendido_neto(producto, fecha_desde=None, fecha_hasta=None):
    qs = Entrega.objects.filter(producto=producto)
    if fecha_desde:
        qs = qs.filter(planilla__fecha__gte=fecha_desde)
    if fecha_hasta:
        qs = qs.filter(planilla__fecha__lte=fecha_hasta)
    return qs.aggregate(t=Sum(F('cantidad') - F('devolucion')))['t'] or 0


def _producido(producto, fecha_desde=None, fecha_hasta=None):
    qs = Produccion.objects.filter(producto=producto)
    if fecha_desde:
        qs = qs.filter(fecha__gte=fecha_desde)
    if fecha_hasta:
        qs = qs.filter(fecha__lte=fecha_hasta)
    return qs.aggregate(t=Sum('cantidad_producida'))['t'] or 0


def detectar_pv(fecha_desde, fecha_hasta):
    """Producción vs Ventas: compara el flujo de un periodo, por producto."""
    hallazgos = []
    for producto in Producto.objects.filter(activo=True):
        producido = _producido(producto, fecha_desde, fecha_hasta)
        vendido = _vendido_neto(producto, fecha_desde, fecha_hasta)

        if producido == 0 and vendido == 0:
            continue

        diferencia = producido - vendido

        if diferencia < 0:
            hallazgos.append({
                'tipo': Descuadre.TipoDescuadre.PRODUCCION_VENTAS,
                'fecha': fecha_hasta,
                'severidad': Descuadre.Severidad.CRITICO,
                'diferencia': Decimal(abs(diferencia)),
                'descripcion': (
                    f'{producto.nombre}: ventas registradas ({vendido}) supera la '
                    f'producción registrada ({producido}) entre {fecha_desde} y '
                    f'{fecha_hasta}. Origen probable: producción no registrada, '
                    f'entrega mal asignada a producto, o error de captura.'
                ),
            })
            continue

        pct = Decimal(diferencia) / Decimal(producido)
        if pct < UMBRAL_LEVE:
            continue

        severidad = (
            Descuadre.Severidad.LEVE if pct < UMBRAL_MODERADO
            else Descuadre.Severidad.MODERADO
        )
        hallazgos.append({
            'tipo': Descuadre.TipoDescuadre.PRODUCCION_VENTAS,
            'fecha': fecha_hasta,
            'severidad': severidad,
            'diferencia': Decimal(diferencia),
            'descripcion': (
                f'{producto.nombre}: producción ({producido}) supera lo vendido '
                f'({vendido}) en un {pct:.0%} entre {fecha_desde} y {fecha_hasta}. '
                f'Origen probable: acumulación de inventario sin vender, producto '
                f'dañado no reportado como avería, o error de captura en entregas.'
            ),
        })
    return hallazgos


UMBRAL_AC_CRITICO = 5  # unidades de diferencia a partir de las cuales AC es crítico


def detectar_ac(fecha_desde, fecha_hasta):
    """Activos vs Clientes — no es literal de HU-13 (ver MODULO_REPORTES.md):
    verifica conservación del conteo físico de cada tipo de activo retornable
    entre el inicio de jornada de fecha_desde y el fin de jornada de
    fecha_hasta. El total (planta lleno + planta vacío + en clientes + baja)
    no debería cambiar salvo por errores de conteo o pérdidas no registradas.
    """
    hallazgos = []
    for tipo, nombre_tipo in ActivoRetornable.TipoActivo.choices:
        inicio = MovimientoActivo.objects.filter(
            tipo_activo=tipo, fecha=fecha_desde,
            momento=MovimientoActivo.Momento.INICIO_JORNADA,
        ).first()
        fin = MovimientoActivo.objects.filter(
            tipo_activo=tipo, fecha=fecha_hasta,
            momento=MovimientoActivo.Momento.FIN_JORNADA,
        ).first()
        if inicio is None or fin is None:
            continue

        diferencia = fin.total - inicio.total
        if diferencia == 0:
            continue

        severidad = (
            Descuadre.Severidad.CRITICO if abs(diferencia) > UMBRAL_AC_CRITICO
            else Descuadre.Severidad.MODERADO
        )
        hallazgos.append({
            'tipo': Descuadre.TipoDescuadre.ACTIVOS_CLIENTES,
            'fecha': fecha_hasta,
            'severidad': severidad,
            'diferencia': Decimal(abs(diferencia)),
            'descripcion': (
                f'{nombre_tipo}: el conteo total de unidades no coincide entre '
                f'el inicio de jornada del {fecha_desde} ({inicio.total}) y el '
                f'fin de jornada del {fecha_hasta} ({fin.total}). Origen '
                f'probable: pérdida física, robo, o error de conteo no '
                f'registrado como baja.'
            ),
        })
    return hallazgos


def detectar_vi(fecha_corte):
    """Ventas vs Inventario: 'disponible' = producido acumulado − vendido
    acumulado histórico hasta la fecha de corte. No hay modelo de stock de
    producto terminado, así que se calcula sobre la marcha en vez de leerse
    de una tabla — ver MODULO_REPORTES.md.
    """
    hallazgos = []
    for producto in Producto.objects.filter(activo=True):
        producido = _producido(producto, fecha_hasta=fecha_corte)
        vendido = _vendido_neto(producto, fecha_hasta=fecha_corte)
        disponible = producido - vendido

        if disponible >= 0:
            continue

        hallazgos.append({
            'tipo': Descuadre.TipoDescuadre.VENTAS_INVENTARIO,
            'fecha': fecha_corte,
            'severidad': Descuadre.Severidad.CRITICO,
            'diferencia': Decimal(abs(disponible)),
            'descripcion': (
                f'{producto.nombre}: inventario disponible acumulado es negativo '
                f'({disponible}) a fecha {fecha_corte} — las ventas históricas '
                f'({vendido}) superan la producción histórica ({producido}). '
                f'Origen probable: acumulación de errores de captura en periodos '
                f'anteriores, o producción/ventas no registradas.'
            ),
        })
    return hallazgos


def ejecutar_deteccion(fecha_desde, fecha_hasta, usuario):
    """Corre los 3 detectores y crea un Descuadre por cada hallazgo nuevo.

    No duplica un hallazgo automático sin resolver que ya describe el mismo
    problema (mismo tipo, fecha y descripción); si ese descuadre anterior ya
    fue resuelto, sí se vuelve a crear — puede ser un problema recurrente.
    """
    hallazgos = (
        detectar_pv(fecha_desde, fecha_hasta)
        + detectar_vi(fecha_hasta)
        + detectar_ac(fecha_desde, fecha_hasta)
    )

    creados = []
    for h in hallazgos:
        ya_existe = Descuadre.objects.filter(
            tipo=h['tipo'], fecha=h['fecha'], descripcion=h['descripcion'],
            es_automatico=True, resuelto=False,
        ).exists()
        if ya_existe:
            continue
        descuadre = Descuadre.objects.create(
            fecha=h['fecha'], tipo=h['tipo'], severidad=h['severidad'],
            descripcion=h['descripcion'], diferencia=h['diferencia'],
            es_automatico=True, detectado_por=usuario,
        )
        creados.append(descuadre)
    return creados
