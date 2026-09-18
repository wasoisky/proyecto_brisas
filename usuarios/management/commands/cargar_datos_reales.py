# -*- coding: utf-8 -*-
"""
Comando: python manage.py cargar_datos_reales --archivo RUTA|-  [--dry-run]
                                              [--reemplazar-demo --confirmar]

Carga los datos base REALES de la empresa (catálogos, insumos, productos, precios,
recetas, clientes, usuarios y conteo inicial de activos) desde un JSON. El JSON
NO va en git (trae clientes y claves): `-` lee de stdin, así no hay que copiarlo
dentro del contenedor:

    docker compose exec -T web python manage.py cargar_datos_reales --archivo - --dry-run < datos.json

Es idempotente: re-ejecutarlo no duplica nada. Por seguridad, el stock inicial de
insumos, el conteo de activos y las claves de usuarios SOLO se escriben al crear
(nunca pisan lo que ya se operó o cambió después).

--reemplazar-demo borra TODOS los datos operativos y los usuarios no-superusuario
antes de cargar (pensado para la primera carga sobre datos demo); exige --confirmar.

Formato del JSON (todas las secciones son opcionales):
  categorias: [{nombre, descripcion}]        unidades: [{nombre, descripcion}]
  insumos:    [{nombre, categoria, unidad, stock_actual, stock_minimo}]
  productos:  [{nombre, presentacion(PAC|BIN|BOT|CAJ|BUL), contenido_cantidad,
                contenido_unidad, unidades_por_empaque, unidad_medida}]
  precios:    [{producto, categoria(REG|MAY), precio}]
  recetas:    [{producto, insumo, cantidad_por_unidad}]
  clientes:   [{nombre, telefono, direccion, categoria, autoriza_datos}]
  usuarios:   [{username, first_name, last_name, rol(ADMIN|PROD|DIST), password}]
  activos:    [{tipo(BOT|CAN), fecha(AAAA-MM-DD), momento(INI|FIN),
                lleno, vacio, clientes}]
"""
import json
import sys
from io import StringIO
from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from activos.models import MovimientoActivo
from distribucion.models import Cliente, PrecioPorCategoria
from produccion.models import (
    CategoriaInsumo, Insumo, Producto, RecetaProducto, Regalia, UnidadMedida,
)
from reportes.models import CierreAnual
from usuarios.management.commands.crear_datos_prueba import Command as ComandoDemo
from usuarios.models import Usuario


class Command(BaseCommand):
    help = 'Carga los datos base reales de la empresa desde un JSON'

    def add_arguments(self, parser):
        parser.add_argument('--archivo', required=True,
                            help='Ruta del JSON, o "-" para leer de stdin')
        parser.add_argument('--dry-run', action='store_true',
                            help='Ejecuta todo y revierte al final (no guarda nada)')
        parser.add_argument('--reemplazar-demo', action='store_true',
                            help='Borra datos operativos y usuarios no-superusuario antes de cargar')
        parser.add_argument('--confirmar', action='store_true',
                            help='Requerido con --reemplazar-demo (salvo con --dry-run)')

    def handle(self, *args, **options):
        if options['reemplazar_demo'] and not (options['confirmar'] or options['dry_run']):
            raise CommandError('--reemplazar-demo borra datos: agrega --confirmar (o prueba con --dry-run).')

        datos = self._leer(options['archivo'])
        self.resumen = {}

        with transaction.atomic():
            if options['reemplazar_demo']:
                self._borrar_datos_operativos()
            self._catalogos(datos)
            self._insumos(datos.get('insumos', []))
            self._productos(datos.get('productos', []))
            self._precios(datos.get('precios', []))
            self._recetas(datos.get('recetas', []))
            self._clientes(datos.get('clientes', []))
            admin = self._usuarios(datos.get('usuarios', []))
            self._activos(datos.get('activos', []), admin)
            if options['dry_run']:
                transaction.set_rollback(True)

        prefijo = '[DRY-RUN, nada se guardó] ' if options['dry_run'] else ''
        self.stdout.write(self.style.SUCCESS(f'\n{prefijo}Resumen de la carga:'))
        for seccion, (creados, actualizados) in self.resumen.items():
            self.stdout.write(f'  {seccion:<12} creados: {creados:<3} actualizados: {actualizados}')

    # ------------------------------------------------------------------ utils
    def _leer(self, archivo):
        try:
            if archivo == '-':
                return json.load(sys.stdin)
            with open(archivo, encoding='utf-8') as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            raise CommandError(f'No se pudo leer el JSON: {exc}')

    def _contar(self, seccion, creado):
        c, a = self.resumen.get(seccion, (0, 0))
        self.resumen[seccion] = (c + 1, a) if creado else (c, a + 1)

    def _buscar(self, modelo, nombre, que):
        obj = modelo.objects.filter(nombre__iexact=nombre.strip()).first()
        if obj is None:
            raise CommandError(f'{que} "{nombre}" no existe (¿falta en el JSON o está mal escrito?).')
        return obj

    def _guardar_por_nombre(self, modelo, seccion, nombre, defaults):
        nombre = nombre.strip()
        obj = modelo.objects.filter(nombre__iexact=nombre).first()
        if obj is None:
            self._contar(seccion, True)
            return modelo.objects.create(nombre=nombre, **defaults)
        for campo, valor in defaults.items():
            setattr(obj, campo, valor)
        obj.save()
        self._contar(seccion, False)
        return obj

    # ---------------------------------------------------------------- secciones
    def _borrar_datos_operativos(self):
        Regalia.objects.all().delete()
        CierreAnual.objects.all().delete()
        ComandoDemo(stdout=StringIO())._limpiar()
        self.stdout.write(self.style.WARNING('Datos operativos y usuarios no-superusuario eliminados.'))

    def _catalogos(self, datos):
        for item in datos.get('categorias', []):
            self._guardar_por_nombre(CategoriaInsumo, 'categorias', item['nombre'],
                                     {'descripcion': item.get('descripcion', '')})
        for item in datos.get('unidades', []):
            self._guardar_por_nombre(UnidadMedida, 'unidades', item['nombre'],
                                     {'descripcion': item.get('descripcion', '')})

    def _insumos(self, items):
        for item in items:
            categoria = self._buscar(CategoriaInsumo, item['categoria'], 'Categoría')
            unidad = self._buscar(UnidadMedida, item['unidad'], 'Unidad')
            existente = Insumo.objects.filter(nombre__iexact=item['nombre'].strip()).first()
            if existente is None:
                Insumo.objects.create(
                    nombre=item['nombre'].strip(), categoria=categoria, unidad_medida=unidad,
                    stock_actual=Decimal(str(item['stock_actual'])),
                    stock_minimo=Decimal(str(item['stock_minimo'])),
                )
                self._contar('insumos', True)
            else:
                existente.categoria, existente.unidad_medida = categoria, unidad
                existente.stock_minimo = Decimal(str(item['stock_minimo']))
                existente.save()
                self._contar('insumos', False)

    def _productos(self, items):
        for item in items:
            unidad_contenido = item.get('contenido_unidad')
            cantidad = item.get('contenido_cantidad')
            self._guardar_por_nombre(Producto, 'productos', item['nombre'], {
                'presentacion': item['presentacion'],
                'contenido_cantidad': Decimal(str(cantidad)) if cantidad is not None else None,
                'contenido_unidad': self._buscar(UnidadMedida, unidad_contenido, 'Unidad')
                if unidad_contenido else None,
                'unidades_por_empaque': item.get('unidades_por_empaque'),
                'unidad_medida': self._buscar(UnidadMedida, item['unidad_medida'], 'Unidad'),
            })

    def _precios(self, items):
        for item in items:
            producto = self._buscar(Producto, item['producto'], 'Producto')
            _, creado = PrecioPorCategoria.objects.update_or_create(
                categoria=item['categoria'], producto=producto,
                defaults={'precio': Decimal(str(item['precio']))},
            )
            self._contar('precios', creado)

    def _recetas(self, items):
        for item in items:
            _, creado = RecetaProducto.objects.update_or_create(
                producto=self._buscar(Producto, item['producto'], 'Producto'),
                insumo=self._buscar(Insumo, item['insumo'], 'Insumo'),
                defaults={'cantidad_por_unidad': Decimal(str(item['cantidad_por_unidad']))},
            )
            self._contar('recetas', creado)

    def _clientes(self, items):
        for item in items:
            self._guardar_por_nombre(Cliente, 'clientes', item['nombre'], {
                'telefono': str(item.get('telefono', '')),
                'direccion': item.get('direccion', ''),
                'categoria': item['categoria'],
                'autoriza_datos': bool(item.get('autoriza_datos', False)),
            })

    def _usuarios(self, items):
        primer_admin = None
        for item in items:
            usuario = Usuario.objects.filter(username__iexact=item['username']).first()
            if usuario is None:
                usuario = Usuario(username=item['username'])
                usuario.set_password(item['password'])
                self._contar('usuarios', True)
            else:
                self._contar('usuarios', False)
            usuario.first_name = item.get('first_name', '')
            usuario.last_name = item.get('last_name', '')
            usuario.rol = item['rol']
            usuario.is_active = True
            usuario.save()
            if primer_admin is None and usuario.rol == Usuario.Rol.ADMINISTRADOR:
                primer_admin = usuario
        return primer_admin or Usuario.objects.filter(rol=Usuario.Rol.ADMINISTRADOR).first()

    def _activos(self, items, admin):
        if items and admin is None:
            raise CommandError('Para cargar activos hace falta al menos un usuario con rol ADMIN.')
        for item in items:
            fecha = date.fromisoformat(item['fecha'])
            existe = MovimientoActivo.objects.filter(
                fecha=fecha, momento=item['momento'], tipo_activo=item['tipo']).exists()
            if existe:
                self._contar('activos', False)
                continue
            movimiento = MovimientoActivo(
                fecha=fecha, momento=item['momento'], tipo_activo=item['tipo'],
                cantidad_en_planta_lleno=item['lleno'],
                cantidad_en_planta_vacio=item['vacio'],
                cantidad_en_clientes=item['clientes'],
                observaciones='Conteo inicial de arranque del sistema',
                registrado_por=admin,
            )
            movimiento.full_clean()
            movimiento.save()
            self._contar('activos', True)
