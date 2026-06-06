# -*- coding: utf-8 -*-
"""
Comando: python manage.py crear_datos_prueba
Carga datos de prueba realistas para Brisas de Pacande.
Idempotente: puede correrse varias veces sin duplicar datos.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand
from django.db import transaction

from usuarios.models import Usuario
from produccion.models import Producto, Insumo, Produccion, ConsumoInsumo, CompraInsumo
from activos.models import MovimientoActivo
from distribucion.models import Cliente, PrecioPorCategoria, Planilla, Entrega, Averia, Credito
from reportes.models import Descuadre


class Command(BaseCommand):
    help = 'Crea datos de prueba para el sistema Brisas de Pacande'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limpiar', action='store_true',
            help='Elimina todos los datos antes de crear los nuevos',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options['limpiar']:
            self._limpiar()

        self.stdout.write('Creando datos de prueba...')

        usuarios  = self._crear_usuarios()
        productos = self._crear_productos()
        insumos   = self._crear_insumos(usuarios['cesar'])
        self._crear_produccion(productos, insumos, usuarios['cesar'])
        clientes  = self._crear_clientes()
        self._crear_precios(productos)
        self._crear_planillas(clientes, productos, usuarios['nicolas'])
        self._crear_activos(usuarios['cesar'])
        self._crear_descuadres(usuarios['maximino'])

        self.stdout.write(self.style.SUCCESS('\nDatos de prueba creados correctamente'))
        self.stdout.write('  Usuarios:')
        self.stdout.write('    maximino / brisas2024  (ADMIN)')
        self.stdout.write('    cesar    / brisas2024  (PROD)')
        self.stdout.write('    nicolas  / brisas2024  (DIST)')

    # -- Limpieza --------------------------------------------------------------

    def _limpiar(self):
        Credito.objects.all().delete()
        Averia.objects.all().delete()
        Entrega.objects.all().delete()
        Planilla.objects.all().delete()
        PrecioPorCategoria.objects.all().delete()
        Cliente.objects.all().delete()
        Descuadre.objects.all().delete()
        MovimientoActivo.objects.all().delete()
        ConsumoInsumo.objects.all().delete()
        Produccion.objects.all().delete()
        CompraInsumo.objects.all().delete()
        Insumo.objects.all().delete()
        Producto.objects.all().delete()
        Usuario.objects.filter(is_superuser=False).delete()
        self.stdout.write(self.style.WARNING('Datos anteriores eliminados.'))

    # -- Usuarios --------------------------------------------------------------

    def _crear_usuarios(self):
        pwd = make_password('brisas2024')

        maximino, _ = Usuario.objects.get_or_create(
            username='maximino',
            defaults=dict(
                first_name='Maximino', last_name='Artunduaga',
                email='maximino@brisaspacande.co',
                rol='ADMIN', password=pwd, is_staff=True,
            ),
        )
        cesar, _ = Usuario.objects.get_or_create(
            username='cesar',
            defaults=dict(
                first_name='Cesar', last_name='Rodriguez',
                email='cesar@brisaspacande.co',
                rol='PROD', password=pwd,
            ),
        )
        nicolas, _ = Usuario.objects.get_or_create(
            username='nicolas',
            defaults=dict(
                first_name='Nicolas', last_name='Palacios',
                email='nicolas@brisaspacande.co',
                rol='DIST', password=pwd,
            ),
        )
        self.stdout.write('  OK Usuarios')
        return {'maximino': maximino, 'cesar': cesar, 'nicolas': nicolas}

    # -- Productos -------------------------------------------------------------

    def _crear_productos(self):
        datos = [
            ('Botellon 20L',  'BOT', 'unidad'),
            ('Paca sin tapa', 'PST', 'paca'),
            ('Paca con tapa', 'PCT', 'paca'),
            ('Bolsa 5L',      'B5L', 'unidad'),
            ('Bolsa 300ml',   'B3C', 'caja'),
            ('Hielo',         'HIE', 'bolsa'),
        ]
        productos = {}
        for nombre, pres, unidad in datos:
            p, _ = Producto.objects.get_or_create(
                presentacion=pres,
                defaults=dict(nombre=nombre, unidad_medida=unidad),
            )
            productos[pres] = p
        self.stdout.write('  OK Productos')
        return productos

    # -- Insumos ---------------------------------------------------------------

    def _crear_insumos(self, cesar):
        datos = [
            ('Plastico sin tapa 500ml', 'PST', 'rollo',  340, 200),
            ('Plastico con tapa 500ml', 'PCT', 'rollo',  280, 200),
            ('Tapas plasticas',         'TAP', 'millar',  15,  10),
            ('Cinta selladora',         'CIN', 'rollo',    8,   5),
            ('Material de reempaque',   'REE', 'kg',       12,   8),
        ]
        insumos = {}
        for nombre, cat, unidad, stock, minimo in datos:
            ins, _ = Insumo.objects.get_or_create(
                nombre=nombre,
                defaults=dict(
                    categoria=cat, unidad_medida=unidad,
                    stock_actual=stock, stock_minimo=minimo,
                ),
            )
            insumos[cat] = ins

        hoy = date.today()
        if not CompraInsumo.objects.filter(registrado_por=cesar).exists():
            CompraInsumo.objects.create(
                fecha=hoy - timedelta(days=5),
                insumo=insumos['PST'], cantidad=500,
                precio_unitario=Decimal('1200'),
                proveedor='Plastificados del Tolima',
                factura='FV-20240601', registrado_por=cesar,
            )
            CompraInsumo.objects.create(
                fecha=hoy - timedelta(days=5),
                insumo=insumos['TAP'], cantidad=30,
                precio_unitario=Decimal('18500'),
                proveedor='Plasticos El Progreso',
                factura='FV-20240602', registrado_por=cesar,
            )

        self.stdout.write('  OK Insumos')
        return insumos

    # -- Produccion ------------------------------------------------------------

    def _crear_produccion(self, productos, insumos, cesar):
        if Produccion.objects.filter(registrado_por=cesar).exists():
            return

        hoy = date.today()
        registros = [
            (hoy - timedelta(days=4), 'BP{}PST'.format((hoy - timedelta(days=4)).strftime('%Y%m%d')), 'PST', 1800),
            (hoy - timedelta(days=3), 'BP{}PCT'.format((hoy - timedelta(days=3)).strftime('%Y%m%d')), 'PCT', 1200),
            (hoy - timedelta(days=2), 'BP{}PST'.format((hoy - timedelta(days=2)).strftime('%Y%m%d')), 'PST', 2000),
            (hoy - timedelta(days=1), 'BP{}PCT'.format((hoy - timedelta(days=1)).strftime('%Y%m%d')), 'PCT', 1500),
            (hoy,                     'BP{}BOT'.format(hoy.strftime('%Y%m%d')),                        'BOT',   45),
        ]

        for fecha, lote, pres, cantidad in registros:
            if Produccion.objects.filter(lote=lote).exists():
                continue
            prod = Produccion.objects.create(
                fecha=fecha, lote=lote,
                producto=productos[pres],
                cantidad_producida=cantidad,
                registrado_por=cesar,
            )
            if pres in ('PST', 'PCT') and 'PST' in insumos:
                ConsumoInsumo.objects.get_or_create(
                    produccion=prod, insumo=insumos['PST'],
                    defaults={'cantidad': Decimal(str(cantidad // 2))},
                )

        self.stdout.write('  OK Produccion')

    # -- Clientes --------------------------------------------------------------

    def _crear_clientes(self):
        datos = [
            ('Minimercado Central',   '3104567890', 'Cra 5 #8-12, Melgar',  'REG', True),
            ('Restaurante La Vista',  '3118923456', 'Cll 3 #10-45, Melgar', 'MAY', True),
            ('Hotel Campestre Sol',   '3125671234', 'Km 2 via Boqueron',    'MAY', True),
            ('Tienda El Manantial',   '3209876543', 'Cra 7 #5-20, Melgar',  'REG', True),
            ('Hostal Rio Verde',      '3001234567', 'Cll 12 #3-10, Melgar', 'REG', False),
            ('Supermercado El Valle', '3154321098', 'Cra 9 #15-30, Melgar', 'MAY', True),
            ('Finca La Esperanza',    '3167890123', 'Km 8 via Chimbi',      'REG', True),
        ]
        clientes = {}
        for nombre, tel, dir_, cat, aut in datos:
            c, _ = Cliente.objects.get_or_create(
                nombre=nombre,
                defaults=dict(telefono=tel, direccion=dir_, categoria=cat, autoriza_datos=aut),
            )
            clientes[nombre] = c
        self.stdout.write('  OK Clientes')
        return clientes

    # -- Precios ---------------------------------------------------------------

    def _crear_precios(self, productos):
        precios = [
            ('REG', 'BOT', Decimal('3500')),
            ('REG', 'PST', Decimal('14500')),
            ('REG', 'PCT', Decimal('16000')),
            ('REG', 'B5L', Decimal('2000')),
            ('REG', 'B3C', Decimal('8500')),
            ('MAY', 'BOT', Decimal('3000')),
            ('MAY', 'PST', Decimal('13000')),
            ('MAY', 'PCT', Decimal('14500')),
            ('MAY', 'B5L', Decimal('1800')),
            ('MAY', 'B3C', Decimal('7500')),
        ]
        for cat, pres, precio in precios:
            if pres in productos:
                PrecioPorCategoria.objects.get_or_create(
                    categoria=cat, producto=productos[pres],
                    defaults={'precio': precio},
                )
        self.stdout.write('  OK Precios por categoria')

    # -- Planillas -------------------------------------------------------------

    def _crear_planillas(self, clientes, productos, nicolas):
        if Planilla.objects.filter(distribuidor=nicolas).exists():
            return

        hoy = date.today()
        nombres = list(clientes.keys())

        configs = [
            (hoy - timedelta(days=3), 'VAL'),
            (hoy - timedelta(days=2), 'VAL'),
            (hoy - timedelta(days=1), 'PEN'),
            (hoy,                     'ABR'),
        ]

        for fecha, estado in configs:
            pl = Planilla.objects.create(
                fecha=fecha, distribuidor=nicolas, estado=estado,
            )

            entregas_data = [
                (nombres[0], 'BOT', 6, 'EFE'),
                (nombres[1], 'PST', 4, 'NEQ'),
                (nombres[2], 'PCT', 3, 'CRE'),
                (nombres[3], 'BOT', 8, 'EFE'),
                (nombres[4], 'BOT', 3, 'CRE'),
            ]

            for nom, pres, cant, pago in entregas_data:
                if pres not in productos:
                    continue
                prod    = productos[pres]
                cliente = clientes[nom]

                try:
                    precio = PrecioPorCategoria.objects.get(
                        categoria=cliente.categoria, producto=prod,
                    ).precio
                except PrecioPorCategoria.DoesNotExist:
                    precio = Decimal('3500')

                entrega = Entrega.objects.create(
                    planilla=pl, cliente=cliente, producto=prod,
                    cantidad=cant, precio_unitario=precio,
                    modalidad_pago=pago, devolucion=0,
                )

                if pago == 'CRE':
                    monto = entrega.subtotal
                    Credito.objects.create(
                        cliente=cliente, entrega=entrega,
                        monto=monto, saldo_pendiente=monto,
                    )

            if estado in ('VAL', 'PEN') and 'BOT' in productos:
                Averia.objects.create(
                    planilla=pl, producto=productos['BOT'],
                    cantidad=1, descripcion='rotura',
                )

        self.stdout.write('  OK Planillas, entregas, creditos')

    # -- Activos ---------------------------------------------------------------

    def _crear_activos(self, cesar):
        if MovimientoActivo.objects.filter(registrado_por=cesar).exists():
            return

        hoy = date.today()
        for delta in range(3, 0, -1):
            fecha = hoy - timedelta(days=delta)
            for momento in ('INI', 'FIN'):
                MovimientoActivo.objects.get_or_create(
                    fecha=fecha, momento=momento, tipo_activo='BOT',
                    defaults=dict(
                        cantidad_en_planta_lleno=62 if momento == 'FIN' else 68,
                        cantidad_en_planta_vacio=28 if momento == 'FIN' else 22,
                        cantidad_en_clientes=30, cantidad_baja=0,
                        registrado_por=cesar,
                    ),
                )
                MovimientoActivo.objects.get_or_create(
                    fecha=fecha, momento=momento, tipo_activo='CAN',
                    defaults=dict(
                        cantidad_en_planta_lleno=0,
                        cantidad_en_planta_vacio=285,
                        cantidad_en_clientes=15, cantidad_baja=0,
                        registrado_por=cesar,
                    ),
                )

        for tipo, lleno, vacio, cli in [('BOT', 70, 20, 30), ('CAN', 0, 290, 10)]:
            MovimientoActivo.objects.get_or_create(
                fecha=hoy, momento='INI', tipo_activo=tipo,
                defaults=dict(
                    cantidad_en_planta_lleno=lleno,
                    cantidad_en_planta_vacio=vacio,
                    cantidad_en_clientes=cli, cantidad_baja=0,
                    registrado_por=cesar,
                ),
            )

        self.stdout.write('  OK Movimientos de activos')

    # -- Descuadres ------------------------------------------------------------

    def _crear_descuadres(self, maximino):
        if Descuadre.objects.filter(detectado_por=maximino).exists():
            return

        hoy = date.today()
        datos = [
            (hoy - timedelta(days=3), 'PV', 'CRI', 'Diferencia de 5 botellones entre produccion y ventas del dia',  Decimal('5'),     False),
            (hoy - timedelta(days=2), 'VI', 'MOD', 'Faltante en efectivo camioneta — diferencia $18,000',           Decimal('18000'), False),
            (hoy - timedelta(days=4), 'AC', 'LEV', 'Diferencia de 3 canastillas en inventario de activos',          Decimal('3'),     True),
        ]

        for fecha, tipo, severidad, desc, dif, resuelto in datos:
            Descuadre.objects.create(
                fecha=fecha, tipo=tipo, severidad=severidad,
                descripcion=desc, diferencia=dif,
                resuelto=resuelto, detectado_por=maximino,
            )

        self.stdout.write('  OK Descuadres')
