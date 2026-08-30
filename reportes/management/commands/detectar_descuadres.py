"""
Comando: python manage.py detectar_descuadres [--fecha-desde AAAA-MM-DD]
          [--fecha-hasta AAAA-MM-DD] [--usuario username]

Corre la detección automática de descuadres (HU-13) para un periodo y crea
los registros de Descuadre encontrados (es_automatico=True). Sin argumentos,
usa el mes en curso y el primer usuario ADMIN activo como detectado_por —
pensado para poder programarse por cron del hosting sin cambiar código.
"""
from datetime import date, datetime

from django.core.management.base import BaseCommand, CommandError

from usuarios.models import Usuario
from reportes.detector import ejecutar_deteccion


class Command(BaseCommand):
    help = 'Ejecuta la detección automática de descuadres (HU-13) para un periodo.'

    def add_arguments(self, parser):
        parser.add_argument('--fecha-desde', type=str, default=None,
                             help='AAAA-MM-DD (default: primer día del mes en curso)')
        parser.add_argument('--fecha-hasta', type=str, default=None,
                             help='AAAA-MM-DD (default: hoy)')
        parser.add_argument('--usuario', type=str, default=None,
                             help='username a registrar como detectado_por (default: primer ADMIN activo)')

    def handle(self, *args, **options):
        hoy = date.today()
        fecha_desde = (
            datetime.strptime(options['fecha_desde'], '%Y-%m-%d').date()
            if options['fecha_desde'] else hoy.replace(day=1)
        )
        fecha_hasta = (
            datetime.strptime(options['fecha_hasta'], '%Y-%m-%d').date()
            if options['fecha_hasta'] else hoy
        )

        if options['usuario']:
            try:
                usuario = Usuario.objects.get(username=options['usuario'])
            except Usuario.DoesNotExist:
                raise CommandError(f"No existe el usuario '{options['usuario']}'")
        else:
            usuario = Usuario.objects.filter(rol='ADMIN', is_active=True).order_by('pk').first()
            if usuario is None:
                raise CommandError(
                    'No hay ningún usuario ADMIN activo para registrar como detectado_por. '
                    'Use --usuario <username>.'
                )

        creados = ejecutar_deteccion(fecha_desde, fecha_hasta, usuario)

        if creados:
            self.stdout.write(self.style.WARNING(
                f'Se detectaron {len(creados)} descuadre(s) entre {fecha_desde} y {fecha_hasta}:'
            ))
            for d in creados:
                self.stdout.write(f'  - [{d.get_severidad_display()}] {d}')
        else:
            self.stdout.write(self.style.SUCCESS(
                f'No se detectaron descuadres nuevos entre {fecha_desde} y {fecha_hasta}.'
            ))
