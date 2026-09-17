from django.core.exceptions import ValidationError
from django.db import models
from django.conf import settings
from produccion.models import Producto


class Cliente(models.Model):
    class Categoria(models.TextChoices):
        REGULAR   = 'REG', 'Regular'
        MAYORISTA = 'MAY', 'Mayorista'

    nombre = models.CharField(max_length=120)
    telefono = models.CharField(max_length=20, blank=True)
    direccion = models.CharField(max_length=200, blank=True)
    categoria = models.CharField(max_length=3, choices=Categoria.choices, default=Categoria.REGULAR)
    # Ley 1581/2012 — autorización tratamiento de datos personales
    autoriza_datos = models.BooleanField(
        default=False,
        verbose_name='Autoriza tratamiento de datos personales (Ley 1581/2012)',
    )
    activo = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Cliente'
        verbose_name_plural = 'Clientes'
        ordering = ['nombre']

    def __str__(self):
        return f'{self.nombre} ({self.get_categoria_display()})'


class PrecioPorCategoria(models.Model):
    """Precio por combinación categoría + producto. No por cliente individual."""
    categoria = models.CharField(max_length=3, choices=Cliente.Categoria.choices)
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT, related_name='precios_categoria')
    precio = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        verbose_name = 'Precio por Categoría'
        verbose_name_plural = 'Precios por Categoría'
        unique_together = ('categoria', 'producto')

    def __str__(self):
        return f'{self.get_categoria_display()} — {self.producto.nombre}: ${self.precio}'


class Planilla(models.Model):
    class Estado(models.TextChoices):
        ABIERTA = 'ABR', 'Abierta'
        PENDIENTE_VALIDACION = 'PEN', 'Pendiente de validación'
        VALIDADA = 'VAL', 'Validada'

    fecha = models.DateField()
    distribuidor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='planillas',
        limit_choices_to={'rol': 'DIST'},
    )
    estado = models.CharField(max_length=3, choices=Estado.choices, default=Estado.ABIERTA)
    observaciones = models.TextField(blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Planilla'
        verbose_name_plural = 'Planillas'
        ordering = ['-fecha', '-creado_en']

    def __str__(self):
        return f'Planilla {self.fecha} — {self.distribuidor.get_full_name() or self.distribuidor.username}'

    def clean(self):
        super().clean()
        from reportes.cierres import validar_periodo_abierto
        validar_periodo_abierto(self.fecha)


class Entrega(models.Model):
    class ModalidadPago(models.TextChoices):
        EFECTIVO = 'EFE', 'Efectivo'
        NEQUI = 'NEQ', 'Nequi'
        CREDITO = 'CRE', 'Crédito'

    planilla = models.ForeignKey(Planilla, on_delete=models.CASCADE, related_name='entregas')
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name='entregas')
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT, related_name='entregas')
    cantidad = models.PositiveIntegerField()
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    modalidad_pago = models.CharField(max_length=3, choices=ModalidadPago.choices)
    devolucion = models.PositiveIntegerField(default=0)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Entrega'
        verbose_name_plural = 'Entregas'
        ordering = ['planilla', 'cliente']

    def __str__(self):
        return f'{self.cliente.nombre} — {self.producto.nombre} x{self.cantidad}'

    @property
    def subtotal(self):
        return (self.cantidad - self.devolucion) * self.precio_unitario

    def clean(self):
        super().clean()
        if self.planilla_id:
            from reportes.cierres import validar_periodo_abierto
            validar_periodo_abierto(self.planilla.fecha)


class Averia(models.Model):
    planilla = models.ForeignKey(Planilla, on_delete=models.CASCADE, related_name='averias')
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT, related_name='averias')
    cantidad = models.PositiveIntegerField()
    descripcion = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Avería'
        verbose_name_plural = 'Averías'

    def __str__(self):
        return f'Avería {self.producto.nombre} x{self.cantidad} — {self.planilla}'

    def clean(self):
        super().clean()
        if self.planilla_id:
            from reportes.cierres import validar_periodo_abierto
            validar_periodo_abierto(self.planilla.fecha)


class Credito(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name='creditos')
    entrega = models.OneToOneField(Entrega, on_delete=models.PROTECT, related_name='credito')
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    saldo_pendiente = models.DecimalField(max_digits=10, decimal_places=2)
    pagado = models.BooleanField(default=False)
    fecha_creacion = models.DateField(auto_now_add=True)
    fecha_pago = models.DateField(null=True, blank=True)

    class Meta:
        verbose_name = 'Crédito'
        verbose_name_plural = 'Créditos'
        ordering = ['pagado', '-fecha_creacion']

    def __str__(self):
        return f'Crédito {self.cliente.nombre} — ${self.saldo_pendiente} pendiente'