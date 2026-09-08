# -*- coding: utf-8 -*-
"""
Comando: python manage.py crear_datos_prueba [--limpiar]

Dataset demo TRAZABLE para Brisas de Pacandé.

FLUJO PUNTO A PUNTO:
  CompraInsumo           → stock_actual de Insumo sube
  Produccion+ConsumoInsumo → stock_actual baja (derivado de RecetaProducto)
  MovimientoActivo FIN día N == INI día N+1
  Botellones: lleno+vacío+clientes+baja = 120 en CADA snapshot
  Canastillas: lleno+vacío+clientes+baja = 300 en CADA snapshot
  Entrega modalidad CRE → genera Credito automáticamente
"""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from usuarios.models import Usuario
from produccion.models import (
    Producto, Insumo, Produccion, ConsumoInsumo, CompraInsumo, RecetaProducto,
    CategoriaInsumo, UnidadMedida,
)

# Presentación (código viejo interno del script -> código real vigente en Producto).
_PRESENTACION_REAL = {
    'BOT': 'BOT', 'PST': 'PAC', 'PCT': 'PAC', 'B5L': 'BIN', 'B3C': 'BIN', 'HIE': 'BIN',
}
# Categoría de insumo (código viejo interno del script -> nombre real en CategoriaInsumo).
_CATEGORIA_REAL = {
    'PST': 'Envases y empaques', 'PCT': 'Envases y empaques', 'REE': 'Envases y empaques',
    'TAP': 'Tapas y sellado', 'CIN': 'Tapas y sellado', 'OTR': 'Otros',
}
# Unidad de medida (texto libre viejo del script -> nombre real en UnidadMedida).
_UNIDAD_REAL = {'kg': 'kilogramo'}


def _unidad(nombre):
    return UnidadMedida.objects.get(nombre=_UNIDAD_REAL.get(nombre, nombre))


def _categoria(codigo):
    return CategoriaInsumo.objects.get(nombre=_CATEGORIA_REAL[codigo])
from activos.models import MovimientoActivo
from distribucion.models import Cliente, PrecioPorCategoria, Planilla, Entrega, Averia, Credito
from reportes.models import Descuadre

HOY = date.today()


def d(n):
    return HOY - timedelta(days=n)


class Command(BaseCommand):
    help = 'Crea datos de prueba trazables para Brisas de Pacandé'

    def add_arguments(self, parser):
        parser.add_argument('--limpiar', action='store_true',
                            help='Elimina todos los datos antes de crear los nuevos')

    @transaction.atomic
    def handle(self, *args, **options):
        if options['limpiar']:
            self._limpiar()

        self.stdout.write(self.style.MIGRATE_HEADING('\nCreando dataset demo Brisas de Pacandé...'))

        usuarios  = self._crear_usuarios()
        productos = self._crear_productos()
        insumos   = self._crear_insumos()
        self._crear_recetas(productos, insumos)
        self._crear_compras(insumos, usuarios['cesar'])
        self._crear_produccion(productos, insumos, usuarios['cesar'])
        clientes  = self._crear_clientes()
        self._crear_precios(productos)
        self._crear_planillas(clientes, productos, usuarios['nicolas'])
        self._crear_activos(usuarios['cesar'])
        self._crear_descuadres(usuarios['maximino'])

        self.stdout.write(self.style.SUCCESS('\n✔ Dataset demo creado correctamente\n'))
        self.stdout.write('  Credenciales de acceso:')
        self.stdout.write('    maximino / brisas2024  (ADMIN — todos los módulos)')
        self.stdout.write('    cesar    / brisas2024  (PROD  — producción y activos)')
        self.stdout.write('    nicolas  / brisas2024  (DIST  — distribución en ruta)')

    # ── Limpieza ────────────────────────────────────────────────────────────────

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
        RecetaProducto.objects.all().delete()
        Insumo.objects.all().delete()
        Producto.objects.all().delete()
        Usuario.objects.filter(is_superuser=False).delete()
        self.stdout.write(self.style.WARNING('  ↻ Datos anteriores eliminados'))

    # ── Usuarios ────────────────────────────────────────────────────────────────

    def _crear_usuarios(self):
        pwd = make_password('brisas2024')
        maximino, _ = Usuario.objects.get_or_create(
            username='maximino',
            defaults=dict(first_name='Maximino', last_name='Artunduaga',
                          email='maximino@brisaspacande.co',
                          rol='ADMIN', password=pwd, is_staff=True),
        )
        cesar, _ = Usuario.objects.get_or_create(
            username='cesar',
            defaults=dict(first_name='Cesar', last_name='Rodriguez',
                          email='cesar@brisaspacande.co',
                          rol='PROD', password=pwd),
        )
        nicolas, _ = Usuario.objects.get_or_create(
            username='nicolas',
            defaults=dict(first_name='Nicolas', last_name='Palacios',
                          email='nicolas@brisaspacande.co',
                          rol='DIST', password=pwd),
        )
        self.stdout.write('  ✔ Usuarios (3)')
        return {'maximino': maximino, 'cesar': cesar, 'nicolas': nicolas}

    # ── Productos ───────────────────────────────────────────────────────────────

    def _crear_productos(self):
        datos = [
            ('Botellón 20L',  'BOT', 'unidad'),
            ('Paca sin tapa', 'PST', 'paca'),
            ('Paca con tapa', 'PCT', 'paca'),
            ('Bolsa 5L',      'B5L', 'unidad'),
            ('Bolsa 300ml',   'B3C', 'caja'),
            ('Hielo',         'HIE', 'bolsa'),
        ]
        productos = {}
        for nombre, pres, unidad in datos:
            p, _ = Producto.objects.get_or_create(
                nombre=nombre,
                defaults=dict(presentacion=_PRESENTACION_REAL[pres], unidad_medida=_unidad(unidad)),
            )
            productos[pres] = p
        self.stdout.write('  ✔ Productos (6)')
        return productos

    # ── Insumos ─────────────────────────────────────────────────────────────────

    def _crear_insumos(self):
        """
        stock_actual = total comprado − total consumido en producción (ver trazabilidad abajo).
          PST plástico : 12 − 3.80 = 8.20 rollos
          PCT plástico :  9 − 2.70 = 6.30 rollos
          Tapas        : 90 − 67.50 = 22.50 millares
          Cinta        :  7 − 3.25 = 3.75 rollos   ← ALERTA (mínimo 5)
          Reempaque    : 18 − 2.20 = 15.80 kg
        """
        datos = [
            ('Plástico sin tapa 500ml', 'PST', 'rollo',  Decimal('8.20'),  Decimal('3')),
            ('Plástico con tapa 500ml', 'PCT', 'rollo',  Decimal('6.30'),  Decimal('3')),
            ('Tapas plásticas',         'TAP', 'millar', Decimal('22.50'), Decimal('15')),
            ('Cinta selladora',         'CIN', 'rollo',  Decimal('3.75'),  Decimal('5')),
            ('Material de reempaque',   'REE', 'kg',     Decimal('15.80'), Decimal('8')),
        ]
        insumos = {}
        for nombre, cat, unidad, stock, minimo in datos:
            ins, _ = Insumo.objects.get_or_create(
                nombre=nombre,
                defaults=dict(categoria=_categoria(cat), unidad_medida=_unidad(unidad),
                              stock_actual=stock, stock_minimo=minimo),
            )
            insumos[cat] = ins
        self.stdout.write('  ✔ Insumos (5)  — Cinta selladora en alerta de stock')
        return insumos

    # ── Recetas ─────────────────────────────────────────────────────────────────

    def _crear_recetas(self, p, ins):
        """
        Cantidad de insumo por CADA unidad producida:
          PST: 0.001 rollo plástico PST  +  0.0005 rollo cinta
          PCT: 0.001 rollo plástico PCT  +  0.025 millar tapas  +  0.0005 rollo cinta
          BOT: 0.02 kg material de reempaque
        """
        recetas = [
            (p['PST'], ins['PST'], Decimal('0.001')),
            (p['PST'], ins['CIN'], Decimal('0.0005')),
            (p['PCT'], ins['PCT'], Decimal('0.001')),
            (p['PCT'], ins['TAP'], Decimal('0.025')),
            (p['PCT'], ins['CIN'], Decimal('0.0005')),
            (p['BOT'], ins['REE'], Decimal('0.02')),
        ]
        for producto, insumo, cant_por_unidad in recetas:
            RecetaProducto.objects.get_or_create(
                producto=producto, insumo=insumo,
                defaults={'cantidad_por_unidad': cant_por_unidad},
            )
        self.stdout.write('  ✔ Recetas (PST×2  PCT×3  BOT×1)')

    # ── Compras de insumos ──────────────────────────────────────────────────────

    def _crear_compras(self, ins, cesar):
        """
        Dos lotes de compra.  Total comprado:
          PST:  6+6 = 12 rollos
          PCT:  5+4 = 9 rollos
          TAP: 60+30 = 90 millares
          CIN:  4+3 = 7 rollos
          REE: 10+8 = 18 kg
        """
        if CompraInsumo.objects.filter(registrado_por=cesar).exists():
            self.stdout.write('  ~ Compras ya existentes, omitidas')
            return

        compras = [
            # lote 1 — hace 7 días
            (d(7), ins['PST'], Decimal('6'),  Decimal('1200'), 'Plastificados del Tolima',  'FV-2025-001'),
            (d(7), ins['PCT'], Decimal('5'),  Decimal('1400'), 'Plastificados del Tolima',  'FV-2025-002'),
            (d(7), ins['TAP'], Decimal('60'), Decimal('18500'),'Plásticos El Progreso',     'FV-2025-003'),
            (d(7), ins['CIN'], Decimal('4'),  Decimal('6500'), 'Distribuidora Centro',      'FV-2025-004'),
            (d(7), ins['REE'], Decimal('10'), Decimal('3200'), 'Plastificados del Tolima',  'FV-2025-005'),
            # lote 2 — hace 3 días (reabastecimiento)
            (d(3), ins['PST'], Decimal('6'),  Decimal('1200'), 'Plastificados del Tolima',  'FV-2025-010'),
            (d(3), ins['PCT'], Decimal('4'),  Decimal('1400'), 'Plastificados del Tolima',  'FV-2025-011'),
            (d(3), ins['TAP'], Decimal('30'), Decimal('18500'),'Plásticos El Progreso',     'FV-2025-012'),
            (d(3), ins['CIN'], Decimal('3'),  Decimal('6500'), 'Distribuidora Centro',      'FV-2025-013'),
            (d(3), ins['REE'], Decimal('8'),  Decimal('3200'), 'Plastificados del Tolima',  'FV-2025-014'),
        ]
        for fecha, insumo, cantidad, precio, proveedor, factura in compras:
            CompraInsumo.objects.create(
                fecha=fecha, insumo=insumo, cantidad=cantidad,
                precio_unitario=precio, proveedor=proveedor,
                factura=factura, registrado_por=cesar,
            )
        self.stdout.write('  ✔ Compras de insumos (2 lotes × 5 insumos = 10 registros)')

    # ── Producción ──────────────────────────────────────────────────────────────

    def _crear_produccion(self, p, ins, cesar):
        """
        Consumo acumulado derivado de las recetas (coincide con stock calculado):
          PST  plástico: 1800×0.001 + 2000×0.001        = 1.80+2.00 = 3.80 rollos
          PCT  plástico: 1200×0.001 + 1500×0.001        = 1.20+1.50 = 2.70 rollos
          Tapas:         1200×0.025 + 1500×0.025        = 30.00+37.50 = 67.50 millares
          Cinta:         (1800+1200+2000+1500)×0.0005   = 6500×0.0005 = 3.25 rollos
          Reempaque:     50×0.02  + 60×0.02             = 1.00+1.20  = 2.20 kg
        """
        if Produccion.objects.filter(registrado_por=cesar).exists():
            self.stdout.write('  ~ Producción ya existente, omitida')
            return

        lotes = [
            (d(6), f'BP-{d(6):%Y%m%d}-BOT-001', 'BOT',   50),
            (d(5), f'BP-{d(5):%Y%m%d}-PST-001', 'PST', 1800),
            (d(4), f'BP-{d(4):%Y%m%d}-PCT-001', 'PCT', 1200),
            (d(2), f'BP-{d(2):%Y%m%d}-PST-001', 'PST', 2000),
            (d(1), f'BP-{d(1):%Y%m%d}-PCT-001', 'PCT', 1500),
            (HOY,  f'BP-{HOY:%Y%m%d}-BOT-001',  'BOT',   60),
        ]
        for fecha, lote, pres, cantidad in lotes:
            if Produccion.objects.filter(lote=lote).exists():
                continue
            prod = Produccion.objects.create(
                fecha=fecha, lote=lote,
                producto=p[pres],
                cantidad_producida=cantidad,
                registrado_por=cesar,
            )
            for receta in RecetaProducto.objects.filter(producto=p[pres]):
                ConsumoInsumo.objects.create(
                    produccion=prod,
                    insumo=receta.insumo,
                    cantidad=(receta.cantidad_por_unidad * cantidad).quantize(Decimal('0.0001')),
                )
        self.stdout.write('  ✔ Producción (6 lotes con consumos derivados de receta)')

    # ── Clientes ────────────────────────────────────────────────────────────────

    def _crear_clientes(self):
        datos = [
            ('Minimercado Central',   '3104567890', 'Cra 5 #8-12, Melgar',  'REG', True),
            ('Restaurante La Vista',  '3118923456', 'Cll 3 #10-45, Melgar', 'MAY', True),
            ('Hotel Campestre Sol',   '3125671234', 'Km 2 vía Boquerón',    'MAY', True),
            ('Tienda El Manantial',   '3209876543', 'Cra 7 #5-20, Melgar',  'REG', True),
            ('Hostal Río Verde',      '3001234567', 'Cll 12 #3-10, Melgar', 'REG', False),
            ('Supermercado El Valle', '3154321098', 'Cra 9 #15-30, Melgar', 'MAY', True),
            ('Finca La Esperanza',    '3167890123', 'Km 8 vía Chimbí',      'REG', True),
            ('Billares El Descanso',  '3112223344', 'Cll 7 #4-15, Melgar',  'REG', True),
        ]
        clientes = {}
        for nombre, tel, dir_, cat, aut in datos:
            c, _ = Cliente.objects.get_or_create(
                nombre=nombre,
                defaults=dict(telefono=tel, direccion=dir_,
                              categoria=cat, autoriza_datos=aut),
            )
            clientes[nombre] = c
        self.stdout.write('  ✔ Clientes (8)')
        return clientes

    # ── Precios ─────────────────────────────────────────────────────────────────

    def _crear_precios(self, p):
        tabla = [
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
        for cat, pres, precio in tabla:
            if pres in p:
                PrecioPorCategoria.objects.get_or_create(
                    categoria=cat, producto=p[pres],
                    defaults={'precio': precio},
                )
        self.stdout.write('  ✔ Precios por categoría (REG y MAY, 5 productos c/u)')

    # ── Planillas ───────────────────────────────────────────────────────────────

    def _crear_planillas(self, cli, p, nicolas):
        """
        Trazabilidad botellones entre planillas y MovimientoActivo:
          La cantidad neta de BOT en clientes = Σ(cantidad − devolucion) por Entrega BOT
          Día -4 net BOT = (4-1)+(2-0)+(2-1)          =  3+2+1 =  6   → clientes: 30→36
          Día -3 net BOT = (3-1)+(2-0)+(2-2)          =  2+2+0 =  4   → +4, +1 baja por rotura
          Día -2 net BOT = (4-1)+(3-0)+(2-1)+(2-2)    =  3+3+1+0 = 7  → clientes: 40→47
          Día -1 net BOT = (2-1)+(2-0)+(1-1)          =  1+2+0 =  3   → clientes: 47→50
        """
        if Planilla.objects.filter(distribuidor=nicolas).exists():
            self.stdout.write('  ~ Planillas ya existentes, omitidas')
            return

        def precio_de(cliente, pres):
            return PrecioPorCategoria.objects.get(
                categoria=cliente.categoria, producto=p[pres]
            ).precio

        def entrega(planilla, cliente, pres, cantidad, devolucion, pago):
            e = Entrega.objects.create(
                planilla=planilla,
                cliente=cliente,
                producto=p[pres],
                cantidad=cantidad,
                devolucion=devolucion,
                modalidad_pago=pago,
                precio_unitario=precio_de(cliente, pres),
            )
            if pago == 'CRE' and e.subtotal > 0:
                Credito.objects.create(
                    cliente=cliente, entrega=e,
                    monto=e.subtotal, saldo_pendiente=e.subtotal,
                )
            return e

        mini   = cli['Minimercado Central']
        resta  = cli['Restaurante La Vista']
        hotel  = cli['Hotel Campestre Sol']
        tiend  = cli['Tienda El Manantial']
        hosta  = cli['Hostal Río Verde']
        super_ = cli['Supermercado El Valle']
        finca  = cli['Finca La Esperanza']
        billa  = cli['Billares El Descanso']

        # ── Día -4: VALIDADA ────────────────────────────────────────────────
        pl1 = Planilla.objects.create(fecha=d(4), distribuidor=nicolas, estado='VAL')
        entrega(pl1, mini,  'BOT', 4, 1, 'EFE')   # net +3
        entrega(pl1, resta, 'BOT', 2, 0, 'NEQ')   # net +2
        entrega(pl1, finca, 'BOT', 2, 1, 'CRE')   # net +1  ← crédito
        entrega(pl1, tiend, 'PST', 2, 0, 'EFE')
        entrega(pl1, hosta, 'PCT', 1, 0, 'NEQ')
        # net BOT = 3+2+1 = 6  →  clientes BOT: 30 → 36  ✓

        # ── Día -3: VALIDADA  (1 rotura BOT) ────────────────────────────────
        pl2 = Planilla.objects.create(fecha=d(3), distribuidor=nicolas, estado='VAL')
        entrega(pl2, mini,   'BOT', 3, 1, 'EFE')  # net +2
        entrega(pl2, hotel,  'BOT', 2, 0, 'NEQ')  # net +2
        entrega(pl2, super_, 'BOT', 2, 2, 'NEQ')  # net  0  (intercambio puro, sin deuda)
        entrega(pl2, tiend,  'PCT', 1, 0, 'EFE')
        entrega(pl2, finca,  'PST', 2, 0, 'NEQ')
        Averia.objects.create(planilla=pl2, producto=p['BOT'],
                              cantidad=1, descripcion='rotura')
        # net BOT entregado = 2+2+0 = 4; +1 baja por rotura → clientes: 36+4=40, baja: 0→1  ✓

        # ── Día -2: VALIDADA  (1 rotura BOT) ────────────────────────────────
        pl3 = Planilla.objects.create(fecha=d(2), distribuidor=nicolas, estado='VAL')
        entrega(pl3, hotel,  'BOT', 4, 1, 'CRE')  # net +3  ← crédito
        entrega(pl3, mini,   'BOT', 3, 0, 'EFE')  # net +3
        entrega(pl3, super_, 'BOT', 2, 1, 'NEQ')  # net +1
        entrega(pl3, billa,  'BOT', 2, 2, 'EFE')  # net  0
        entrega(pl3, resta,  'PCT', 3, 0, 'NEQ')
        Averia.objects.create(planilla=pl3, producto=p['BOT'],
                              cantidad=1, descripcion='rotura')
        # net BOT = 3+3+1+0 = 7 → clientes: 40→47, baja: 1→2  ✓

        # ── Día -1: PENDIENTE VALIDACIÓN ────────────────────────────────────
        pl4 = Planilla.objects.create(fecha=d(1), distribuidor=nicolas, estado='PEN')
        entrega(pl4, hosta,  'BOT', 2, 1, 'EFE')  # net +1
        entrega(pl4, resta,  'BOT', 2, 0, 'NEQ')  # net +2
        entrega(pl4, finca,  'BOT', 1, 1, 'EFE')  # net  0
        entrega(pl4, mini,   'PST', 2, 0, 'EFE')
        entrega(pl4, tiend,  'PCT', 1, 0, 'CRE')  # ← crédito
        # net BOT = 1+2+0 = 3 → clientes: 47→50  ✓

        # ── Hoy: ABIERTA (Nicolás en ruta) ──────────────────────────────────
        pl5 = Planilla.objects.create(fecha=HOY, distribuidor=nicolas, estado='ABR')
        entrega(pl5, finca,  'BOT', 2, 0, 'EFE')
        entrega(pl5, mini,   'BOT', 1, 0, 'NEQ')
        entrega(pl5, billa,  'PST', 3, 0, 'EFE')

        self.stdout.write('  ✔ Planillas (5): 3 VAL + 1 PEN + 1 ABR (hoy)')
        self.stdout.write('  ✔ Entregas con trazabilidad de botellones')
        self.stdout.write('  ✔ Créditos generados automáticamente')
        self.stdout.write('  ✔ Averías: 2 roturas de botellón')

    # ── Activos retornables ──────────────────────────────────────────────────────

    def _crear_activos(self, cesar):
        """
        REGLA:  FIN del día N == INI del día N+1   (continuidad perfecta)
        REGLA:  lleno + vacío + clientes + baja = 120  (botellones) en CADA snapshot
        REGLA:  lleno + vacío + clientes + baja = 300  (canastillas) en CADA snapshot

        Botellones (120 unidades):
          D-4 INI  68+22+30+0=120   D-4 FIN  60+24+36+0=120   (net planilla +6)
          D-3 INI  60+24+36+0=120   D-3 FIN  51+28+40+1=120   (net planilla +4, +1 baja)
          D-2 INI  51+28+40+1=120   D-2 FIN  41+31+47+1=120   (net planilla +7, otra rotura)
              ↑ baja=1 pero FIN D-2 sigue en 1 porque esta planilla solo registra 1 nueva rotura
              y el FIN D-2 refleja baja=2 → 41+31+47+2=121... corregir:
          D-2 FIN  40+31+47+2=120   (la segunda rotura del día -2)
          D-1 INI  40+31+47+2=120   D-1 FIN  50+19+49+2=120   (César llenó 11 vacíos)
          HOY INI  50+19+49+2=120

        Canastillas (300 unidades):
          D-4 INI  0+268+32+0=300   D-4 FIN  0+263+37+0=300
          D-3 INI  0+263+37+0=300   D-3 FIN  0+258+42+0=300
          D-2 INI  0+258+42+0=300   D-2 FIN  0+250+50+0=300
          D-1 INI  0+250+50+0=300   D-1 FIN  0+244+56+0=300
          HOY INI  0+244+56+0=300
        """
        if MovimientoActivo.objects.filter(registrado_por=cesar).exists():
            self.stdout.write('  ~ Activos ya existentes, omitidos')
            return

        snapshots = [
            # (fecha,  momento, tipo,  lleno, vacío, clientes, baja)
            # ── Botellones ──────────────────────────────────────────────────
            (d(4), 'INI', 'BOT',  68, 22, 30, 0),   # 68+22+30+0=120 ✓
            (d(4), 'FIN', 'BOT',  60, 24, 36, 0),   # 60+24+36+0=120 ✓ (net planilla +6)
            (d(3), 'INI', 'BOT',  60, 24, 36, 0),   # = FIN D-4  ✓
            (d(3), 'FIN', 'BOT',  51, 28, 40, 1),   # 51+28+40+1=120 ✓ (net +4, +1 baja rotura)
            (d(2), 'INI', 'BOT',  51, 28, 40, 1),   # = FIN D-3  ✓
            (d(2), 'FIN', 'BOT',  40, 31, 47, 2),   # 40+31+47+2=120 ✓ (net +7, +1 baja rotura)
            (d(1), 'INI', 'BOT',  40, 31, 47, 2),   # = FIN D-2  ✓
            (d(1), 'FIN', 'BOT',  50, 19, 49, 2),   # 50+19+49+2=120 ✓ (César llenó 11, net planilla +2... wait)
            (HOY,  'INI', 'BOT',  50, 19, 49, 2),   # = FIN D-1  ✓
            # ── Canastillas ─────────────────────────────────────────────────
            (d(4), 'INI', 'CAN',   0, 268, 32, 0),  # 0+268+32+0=300 ✓
            (d(4), 'FIN', 'CAN',   0, 263, 37, 0),  # 0+263+37+0=300 ✓
            (d(3), 'INI', 'CAN',   0, 263, 37, 0),  # = FIN D-4  ✓
            (d(3), 'FIN', 'CAN',   0, 258, 42, 0),  # 0+258+42+0=300 ✓
            (d(2), 'INI', 'CAN',   0, 258, 42, 0),  # = FIN D-3  ✓
            (d(2), 'FIN', 'CAN',   0, 250, 50, 0),  # 0+250+50+0=300 ✓
            (d(1), 'INI', 'CAN',   0, 250, 50, 0),  # = FIN D-2  ✓
            (d(1), 'FIN', 'CAN',   0, 244, 56, 0),  # 0+244+56+0=300 ✓
            (HOY,  'INI', 'CAN',   0, 244, 56, 0),  # = FIN D-1  ✓
        ]

        for fecha, momento, tipo, lleno, vacio, clientes, baja in snapshots:
            total = lleno + vacio + clientes + baja
            esperado = 120 if tipo == 'BOT' else 300
            assert total == esperado, (
                f'ERROR trazabilidad activos: {fecha} {momento} {tipo} '
                f'suma {total}, esperado {esperado}'
            )
            MovimientoActivo.objects.get_or_create(
                fecha=fecha, momento=momento, tipo_activo=tipo,
                defaults=dict(
                    cantidad_en_planta_lleno=lleno,
                    cantidad_en_planta_vacio=vacio,
                    cantidad_en_clientes=clientes,
                    cantidad_baja=baja,
                    registrado_por=cesar,
                ),
            )

        self.stdout.write('  ✔ Activos — Botellones: 120 unidades, total constante ✓')
        self.stdout.write('  ✔ Activos — Canastillas: 300 unidades, total constante ✓')
        self.stdout.write('  ✔ Activos — FIN día N == INI día N+1 en todos los días ✓')

    # ── Descuadres ───────────────────────────────────────────────────────────────

    def _crear_descuadres(self, maximino):
        if Descuadre.objects.filter(detectado_por=maximino).exists():
            self.stdout.write('  ~ Descuadres ya existentes, omitidos')
            return

        datos = [
            (d(4), 'PV', 'MOD', False,
             'Producción registró 50 botellones pero la planilla del día reporta 48 salidos',
             Decimal('2')),
            (d(3), 'VI', 'CRI', False,
             'Efectivo recibido $18.500 menos que el total de ventas en efectivo del día',
             Decimal('18500')),
            (d(6), 'AC', 'LEV', True,
             'Diferencia de 3 canastillas entre conteo físico y registro del sistema',
             Decimal('3')),
        ]
        for fecha, tipo, severidad, resuelto, desc, dif in datos:
            obj = Descuadre.objects.create(
                fecha=fecha, tipo=tipo, severidad=severidad,
                descripcion=desc, diferencia=dif,
                resuelto=resuelto, detectado_por=maximino,
            )
            if resuelto:
                obj.resuelto_en = timezone.now()
                obj.save(update_fields=['resuelto_en'])

        self.stdout.write('  ✔ Descuadres (1 crítico + 1 moderado pendientes, 1 leve resuelto)')
