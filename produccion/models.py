from django.db import models
from django.conf import settings


class CategoriaInsumo(models.Model):
    """Catálogo editable de categorías de insumo (admin, sin tocar código)."""
    nombre = models.CharField(max_length=60, unique=True)
    descripcion = models.CharField(max_length=200, blank=True)
    activo = models.BooleanField(default=True)
    orden = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = 'Categoría de Insumo'
        verbose_name_plural = 'Categorías de Insumo'
        ordering = ['orden', 'nombre']

    def __str__(self):
        return self.nombre


class UnidadMedida(models.Model):
    """Catálogo editable de unidades de medida (admin, sin tocar código)."""
    nombre = models.CharField(max_length=40, unique=True)
    descripcion = models.CharField(max_length=200, blank=True)
    activo = models.BooleanField(default=True)
    orden = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = 'Unidad de Medida'
        verbose_name_plural = 'Unidades de Medida'
        ordering = ['orden', 'nombre']

    def __str__(self):
        return self.nombre


def _default_unidad_medida_producto():
    """Mismo default que tenía el CharField viejo ('unidad'), ahora vía catálogo."""
    return UnidadMedida.objects.filter(nombre='unidad').values_list('pk', flat=True).first()


class Producto(models.Model):
    class Presentacion(models.TextChoices):
        PACA = 'PAC', 'Paca'
        BOLSA_INDIVIDUAL = 'BIN', 'Bolsa individual'
        BOTELLON = 'BOT', 'Botellón'
        CAJA = 'CAJ', 'Caja'
        BULTO = 'BUL', 'Bulto'

    nombre = models.CharField(max_length=60, help_text='Ej: Agua sin tapa, Agua con tapa, Hielo')
    presentacion = models.CharField(
        max_length=3, choices=Presentacion.choices,
        help_text='Forma de empaque del producto terminado',
    )
    contenido_cantidad = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        help_text='Ej: 300 (junto con la unidad de contenido, ej. ml)',
    )
    contenido_unidad = models.ForeignKey(
        UnidadMedida, on_delete=models.PROTECT, null=True, blank=True,
        related_name='productos_contenido',
        help_text='Unidad del contenido individual (ej. ml, L, kg)',
    )
    unidades_por_empaque = models.PositiveIntegerField(
        null=True, blank=True,
        help_text='Ej: 20, 25, 28 — cuántas unidades individuales trae el empaque (opcional)',
    )
    unidad_medida = models.ForeignKey(
        UnidadMedida, on_delete=models.PROTECT, related_name='productos_unidad',
        default=_default_unidad_medida_producto,
        help_text='Unidad en que se cuenta el producto terminado (normalmente "unidad")',
    )
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Producto'
        verbose_name_plural = 'Productos'
        ordering = ['presentacion']

    def __str__(self):
        return self.nombre


class Insumo(models.Model):
    nombre = models.CharField(max_length=60, help_text='Ej: Tapas plásticas, Cinta selladora')
    categoria = models.ForeignKey(
        CategoriaInsumo, on_delete=models.PROTECT, related_name='insumos',
        help_text='Ej: Tapas y sellado — tapas plásticas, anillos de sellado, cinta selladora',
    )
    unidad_medida = models.ForeignKey(
        UnidadMedida, on_delete=models.PROTECT, related_name='insumos',
        help_text='Ej: rollo, kilogramo, millar',
    )
    stock_actual = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                       help_text='Ej: 8.20')
    stock_minimo = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                       help_text='Cantidad mínima antes de generar alerta. Ej: 3')
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Insumo'
        verbose_name_plural = 'Insumos'
        ordering = ['nombre']

    def __str__(self):
        return f'{self.nombre} ({self.stock_actual} {self.unidad_medida})'

    @property
    def alerta_stock(self):
        return self.stock_actual <= self.stock_minimo


class Produccion(models.Model):
    fecha = models.DateField()
    lote = models.CharField(max_length=30, unique=True,
                            help_text='Código de lote — Res. 2674/2013 BPM')
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT,
                                 related_name='registros_produccion')
    cantidad_producida = models.PositiveIntegerField()
    observaciones = models.TextField(blank=True)
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='producciones_registradas',
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Registro de Producción'
        verbose_name_plural = 'Registros de Producción'
        ordering = ['-fecha', '-creado_en']

    def __str__(self):
        return f'Lote {self.lote} — {self.producto} ({self.cantidad_producida})'


class ConsumoInsumo(models.Model):
    """Insumos consumidos en un registro de producción."""
    produccion = models.ForeignKey(Produccion, on_delete=models.CASCADE,
                                   related_name='consumos')
    insumo = models.ForeignKey(Insumo, on_delete=models.PROTECT,
                               related_name='consumos')
    cantidad = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        verbose_name = 'Consumo de Insumo'
        verbose_name_plural = 'Consumos de Insumos'
        unique_together = ('produccion', 'insumo')

    def __str__(self):
        return f'{self.insumo.nombre} — {self.cantidad} {self.insumo.unidad_medida}'


class RecetaProducto(models.Model):
    """Cantidad de cada insumo necesaria por unidad producida de un producto."""
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE,
                                 related_name='receta')
    insumo = models.ForeignKey(Insumo, on_delete=models.PROTECT,
                               related_name='recetas')
    cantidad_por_unidad = models.DecimalField(
        max_digits=10, decimal_places=4,
        help_text='Cantidad de este insumo por cada unidad producida'
    )

    class Meta:
        verbose_name = 'Receta de Producto'
        verbose_name_plural = 'Recetas de Productos'
        unique_together = ('producto', 'insumo')
        ordering = ['producto', 'insumo']

    def __str__(self):
        return f'{self.producto.nombre} → {self.insumo.nombre} ({self.cantidad_por_unidad}/u)'


class CompraInsumo(models.Model):
    fecha = models.DateField()
    insumo = models.ForeignKey(Insumo, on_delete=models.PROTECT,
                               related_name='compras')
    cantidad = models.DecimalField(max_digits=10, decimal_places=2)
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    proveedor = models.CharField(max_length=100, blank=True)
    factura = models.CharField(max_length=50, blank=True,
                               help_text='Número de factura o remisión')
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='compras_registradas',
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Compra de Insumo'
        verbose_name_plural = 'Compras de Insumos'
        ordering = ['-fecha']

    def __str__(self):
        return f'{self.fecha} — {self.insumo.nombre} x{self.cantidad}'

    @property
    def total(self):
        return self.cantidad * self.precio_unitario


class Regalia(models.Model):
    """Producto terminado entregado sin cobro: obsequio, cortesía o promoción."""
    class Motivo(models.TextChoices):
        PROMOCION = 'PRO', 'Promoción'
        OBSEQUIO_CLIENTE = 'OBS', 'Obsequio a cliente'
        CORTESIA = 'COR', 'Cortesía institucional'
        OTRO = 'OTR', 'Otro'

    fecha = models.DateField()
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT,
                                 related_name='regalias')
    produccion = models.ForeignKey(
        Produccion, on_delete=models.PROTECT, related_name='regalias',
        null=True, blank=True,
        help_text='Lote de origen, si se conoce (trazabilidad BPM — Res. 2674/2013)',
    )
    cantidad = models.PositiveIntegerField()
    destinatario = models.CharField(max_length=100, blank=True,
                                    help_text='A quién se le entregó (opcional)')
    motivo = models.CharField(max_length=3, choices=Motivo.choices, default=Motivo.OTRO)
    observaciones = models.TextField(blank=True)
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='regalias_registradas',
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Regalía'
        verbose_name_plural = 'Regalías'
        ordering = ['-fecha', '-creado_en']

    def __str__(self):
        return f'{self.fecha} — {self.producto} x{self.cantidad} ({self.get_motivo_display()})'