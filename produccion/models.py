from django.db import models
from django.conf import settings


class Producto(models.Model):
    class Presentacion(models.TextChoices):
        PACA_SIN_TAPA = 'PST', 'Paca sin tapa'
        PACA_CON_TAPA = 'PCT', 'Paca con tapa'
        BOTELLON = 'BOT', 'Botellón 20L'
        BOLSA_5L = 'B5L', 'Bolsa 5L'
        BOLSA_300ML = 'B3C', 'Bolsa 300ml'
        HIELO = 'HIE', 'Hielo'

    nombre = models.CharField(max_length=60)
    presentacion = models.CharField(max_length=3, choices=Presentacion.choices)
    unidad_medida = models.CharField(max_length=20, default='unidad')
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Producto'
        verbose_name_plural = 'Productos'
        ordering = ['presentacion']

    def __str__(self):
        return self.nombre


class Insumo(models.Model):
    class Categoria(models.TextChoices):
        PLASTICO_SIN_TAPA = 'PST', 'Plástico sin tapa'
        PLASTICO_CON_TAPA = 'PCT', 'Plástico con tapa'
        TAPA = 'TAP', 'Tapas'
        REEMPAQUE = 'REE', 'Material de reempaque'
        CINTA = 'CIN', 'Cinta'
        OTRO = 'OTR', 'Otro'

    nombre = models.CharField(max_length=60)
    categoria = models.CharField(max_length=3, choices=Categoria.choices)
    unidad_medida = models.CharField(max_length=20)
    stock_actual = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    stock_minimo = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                       help_text='Cantidad mínima antes de generar alerta')
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