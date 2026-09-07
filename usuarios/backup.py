# -*- coding: utf-8 -*-
"""
Lógica de backup de PostgreSQL, compartida entre el management command
`backup_bd` y la vista web de backups (solo superusuarios).
"""
import os
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from django.conf import settings

POSTGRES_ENGINE = 'django.db.backends.postgresql'


class BackupError(Exception):
    """Se lanza cuando no se puede generar el backup (motor no soportado o pg_dump falla)."""


def get_backup_dir():
    return Path(settings.BASE_DIR) / 'backups'


def generar_backup(destino=None):
    """Genera un dump de PostgreSQL con pg_dump (-F c) y devuelve la ruta del archivo."""
    db = settings.DATABASES['default']
    if db['ENGINE'] != POSTGRES_ENGINE:
        raise BackupError('El backup solo soporta PostgreSQL (django.db.backends.postgresql).')

    destino = Path(destino or get_backup_dir())
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

    try:
        resultado = subprocess.run(comando, env=env, capture_output=True, text=True)
    except FileNotFoundError as e:
        raise BackupError(
            "No se encontró el ejecutable 'pg_dump'. Verifica que PostgreSQL esté "
            "instalado y que su carpeta bin (ej. C:\\Program Files\\PostgreSQL\\18\\bin "
            "en Windows) esté en el PATH del sistema."
        ) from e

    if resultado.returncode != 0:
        raise BackupError(f'pg_dump falló: {resultado.stderr.strip()}')

    return archivo


@dataclass
class BackupInfo:
    nombre: str
    tamano: int
    fecha: datetime


def listar_backups():
    """Lista los dumps en BASE_DIR/backups, más reciente primero."""
    directorio = get_backup_dir()
    if not directorio.exists():
        return []
    backups = []
    for archivo in directorio.iterdir():
        if archivo.is_file():
            stat = archivo.stat()
            backups.append(BackupInfo(
                nombre=archivo.name,
                tamano=stat.st_size,
                fecha=datetime.fromtimestamp(stat.st_mtime),
            ))
    return sorted(backups, key=lambda b: b.fecha, reverse=True)
