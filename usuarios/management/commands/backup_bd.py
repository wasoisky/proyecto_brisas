# -*- coding: utf-8 -*-
"""
Comando: python manage.py backup_bd [--destino RUTA]

Genera un dump de PostgreSQL con pg_dump (formato custom, -F c).
Tratamiento del riesgo crítico "pérdida de información por ausencia de
copias de seguridad" (documento de tesis §13.3, nivel 15).

Lógica compartida con la vista web de backups (solo superusuarios) en
usuarios/backup.py — ver generar_backup()/listar_backups().

Procedimiento de restauración:
    pg_restore --clean --if-exists -h HOST -p PORT -U USER -d NOMBRE_BD archivo.dump

Programación periódica sugerida (no se ofrece desde la web a propósito):
  - Linux/cron:          0 3 * * * cd /ruta/proyecto && venv/bin/python manage.py backup_bd
  - Windows Task Scheduler: acción diaria ejecutando
      venv\\Scripts\\python.exe manage.py backup_bd
    con directorio de inicio en la raíz del proyecto.
"""
from django.core.management.base import BaseCommand, CommandError

from usuarios.backup import BackupError, generar_backup


class Command(BaseCommand):
    help = 'Genera un dump de PostgreSQL (pg_dump) para respaldo periódico.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--destino',
            default=None,
            help='Carpeta donde se guarda el dump (default: BASE_DIR/backups).',
        )

    def handle(self, *args, **options):
        try:
            archivo = generar_backup(destino=options['destino'])
        except BackupError as e:
            raise CommandError(str(e))

        self.stdout.write(self.style.SUCCESS(f'Backup generado: {archivo}'))
