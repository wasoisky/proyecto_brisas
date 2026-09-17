from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError


class ActivoRetornable(models.Model):
    class TipoActivo(models.TextChoices):
        BOTELLON = 'BOT', 'Botellón 20L'
        CANASTILLA = 'CAN', 'Canastilla'

    class Estado(models.TextChoices):
        EN_PLANTA_LLENO = 'PLL', 'En planta — lleno'
        EN_PLANTA_VACIO = 'PVA', 'En planta — vacío'
        EN_CLIENTE = 'CLI', 'En poder de cliente'
        DADO_DE_BAJA = 'BAJ', 'Dado de baja'

    tipo = models.CharField(max_length=3, choices=TipoActivo.choices)
    estado = models.CharField(max_length=3, choices=Estado.choices, default=Estado.EN_PLANTA_VACIO)
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Activo Retornable'
        verbose_name_plural = 'Activos Retornables'
        ordering = ['tipo', 'estado']

    def __str__(self):
        return f'{self.get_tipo_display()} — {self.get_estado_display()}'


class MovimientoActivo(models.Model):
    class Momento(models.TextChoices):
        INICIO_JORNADA = 'INI', 'Inicio de jornada'
        FIN_JORNADA = 'FIN', 'Fin de jornada'

    fecha = models.DateField()
    momento = models.CharField(max_length=3, choices=Momento.choices)
    tipo_activo = models.CharField(max_length=3, choices=ActivoRetornable.TipoActivo.choices)

    # Conteos agregados por estado (trazabilidad por cliente es agregada, sin marca individual)
    cantidad_en_planta_lleno = models.PositiveIntegerField(default=0)
    cantidad_en_planta_vacio = models.PositiveIntegerField(default=0)
    cantidad_en_clientes = models.PositiveIntegerField(default=0)
    cantidad_baja = models.PositiveIntegerField(default=0)

    observaciones = models.TextField(blank=True)
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='movimientos_activos',
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Movimiento de Activo'
        verbose_name_plural = 'Movimientos de Activos'
        ordering = ['-fecha', 'momento']
        unique_together = ('fecha', 'momento', 'tipo_activo')

    def __str__(self):
        return f'{self.fecha} {self.get_momento_display()} — {self.get_tipo_activo_display()}'

    @property
    def total(self):
        return (self.cantidad_en_planta_lleno + self.cantidad_en_planta_vacio
                + self.cantidad_en_clientes + self.cantidad_baja)

    def clean(self):
        super().clean()
        from reportes.cierres import validar_periodo_abierto
        validar_periodo_abierto(self.fecha)


class BajaActivo(models.Model):
    class Motivo(models.TextChoices):
        ROTURA = 'ROT', 'Rotura'
        PERDIDA = 'PER', 'Pérdida'
        ROBO = 'ROB', 'Robo'
        DETERIORO = 'DET', 'Deterioro'
        OTRO = 'OTR', 'Otro'

    movimiento = models.ForeignKey(
        MovimientoActivo, on_delete=models.CASCADE, related_name='bajas',
    )
    cantidad = models.PositiveIntegerField()
    motivo = models.CharField(max_length=3, choices=Motivo.choices, default=Motivo.ROTURA)
    descripcion = models.TextField(blank=True)
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='bajas_activos',
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Baja de Activo'
        verbose_name_plural = 'Bajas de Activos'
        ordering = ['-creado_en']

    def __str__(self):
        return (f'Baja {self.movimiento.get_tipo_activo_display()} '
                f'x{self.cantidad} — {self.get_motivo_display()}')