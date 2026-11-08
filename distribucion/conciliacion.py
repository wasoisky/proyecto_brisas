"""Cálculos de la ruta: conciliación de una planilla y stock disponible en planta.

Nada se guarda: todo se deriva de Produccion, CargaRuta, Entrega, Averia y Regalia.
"""
from django.db.models import F, Sum

from produccion.models import Producto, Produccion, Regalia

from .models import Averia, CargaRuta, Entrega


def resumen_planilla(planilla):
    """Una fila por producto con carga, entrega o avería en la planilla.

    queda      = cargado - entregado - averiado   (lo que debería seguir en el camión)
    diferencia = queda - devuelto                 (>0 faltante, <0 sobrante, None sin cierre)
    """
    filas = {}

    def fila(producto):
        return filas.setdefault(producto.pk, {
            'producto': producto, 'cargado': 0, 'entregado': 0, 'averiado': 0, 'devuelto': None,
        })

    for c in CargaRuta.objects.filter(planilla=planilla).select_related('producto'):
        f = fila(c.producto)
        f['cargado'] = c.cantidad_cargada
        f['devuelto'] = c.cantidad_devuelta
    for e in Entrega.objects.filter(planilla=planilla).select_related('producto'):
        fila(e.producto)['entregado'] += e.cantidad - e.devolucion   # neto, por entregas heredadas
    for a in Averia.objects.filter(planilla=planilla).select_related('producto'):
        fila(a.producto)['averiado'] += a.cantidad

    resultado = []
    for f in filas.values():
        f['queda'] = f['cargado'] - f['entregado'] - f['averiado']
        f['diferencia'] = None if f['devuelto'] is None else f['queda'] - f['devuelto']
        resultado.append(f)
    return sorted(resultado, key=lambda f: f['producto'].nombre)


def disponible_en_planta(producto):
    """producido - cargado + devuelto - regalías (todas las planillas, sin guardar nada)."""
    producido = Produccion.objects.filter(producto=producto).aggregate(t=Sum('cantidad_producida'))['t'] or 0
    cargas = CargaRuta.objects.filter(producto=producto).aggregate(
        c=Sum('cantidad_cargada'), d=Sum('cantidad_devuelta'))
    regalado = Regalia.objects.filter(producto=producto).aggregate(t=Sum('cantidad'))['t'] or 0
    return producido - (cargas['c'] or 0) + (cargas['d'] or 0) - regalado
