# -*- coding: utf-8 -*-
"""
Comando: python manage.py backup_bd [--destino RUTA]

Genera un dump de PostgreSQL con pg_dump (formato custom, -F c).
Tratamiento del riesgo crítico "pérdida de información por ausencia de
copias de seguridad" (documento de tesis §13.3, nivel 15).

Procedimiento de restauración:
    pg_restore --clean --if-exists -h HOST -p PORT -U USER -d NOMBRE_BD archivo.dump

Programación periódica sugerida:
  - Linux/cron:          0 3 * * * cd /ruta/proyecto && venv/bin/python manage.py backup_bd
  - Windows Task Scheduler: acción diaria ejecutando
      venv\\Scripts\\python.exe manage.py backup_bd
    con directorio de inicio en la raíz del proyecto.
"""
import os
import subprocess
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

POSTGRES_ENGINE = 'django.db.backends.postgresql'


class Command(BaseCommand):
    help = 'Genera un dump de PostgreSQL (pg_dump) para respaldo periódico.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--destino',
            default=None,
            help='Carpeta donde se guarda el dump (default: BASE_DIR/backups).',
        )

    def handle(self, *args, **options):
        db = settings.DATABASES['default']
        if db['ENGINE'] != POSTGRES_ENGINE:
            raise CommandError('backup_bd solo soporta PostgreSQL (django.db.backends.postgresql).')

        destino = Path(options['destino'] or (settings.BASE_DIR / 'backups'))
        destino.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        archivo = destino / f'brisas_pacande_{timestamp}.dump'

        comando = [
            'pg_dump',
            '-h', db['HOST'] or 'localhost',
            '-p', str(db['PORT'] or 5432),
            '-U', db['USER'],
            '-F', 'c',
            '-f', str(archivo),
            db['NAME'],
        ]

        env = os.environ.copy()
        if db.get('PASSWORD'):
            env['PGPASSWORD'] = db['PASSWORD']

        resultado = subprocess.run(comando, env=env, capture_output=True, text=True)
        if resultado.returncode != 0:
            raise CommandError(f'pg_dump falló: {resultado.stderr.strip()}')

        self.stdout.write(self.style.SUCCESS(f'Backup generado: {archivo}'))
