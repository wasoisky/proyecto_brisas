from django.core.exceptions import ValidationError

from .models import CierreAnual


def anio_cerrado(anio):
    """True si existe un CierreAnual para ese año con cerrado=True."""
    return CierreAnual.objects.filter(anio=anio, cerrado=True).exists()


def validar_periodo_abierto(fecha):
    """Lanza ValidationError si `fecha` cae en un año ya cerrado.

    No hace nada si `fecha` es None (el llamador es responsable de decidir
    si una fecha ausente es válida en su propio contexto).
    """
    if fecha is None:
        return
    if anio_cerrado(fecha.year):
        raise ValidationError(
            f'El año {fecha.year} ya está cerrado. No se pueden crear ni '
            f'modificar registros de ese periodo.'
        )
