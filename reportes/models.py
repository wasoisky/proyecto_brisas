from django.db import models
from django.conf import settings


class Descuadre(models.Model):
    class TipoDescuadre(models.TextChoices):
        PRODUCCION_VENTAS = 'PV', 'Producción vs Ventas'
        VENTAS_INVENTARIO = 'VI', 'Ventas vs Inventario'
        ACTIVOS_CLIENTES = 'AC', 'Activos vs Clientes'

    class Severidad(models.TextChoices):
        LEVE = 'LEV', 'Leve'
        MODERADO = 'MOD', 'Moderado'
        CRITICO = 'CRI', 'Crítico'

    fecha = models.DateField()
    tipo = models.CharField(max_length=2, choices=TipoDescuadre.choices)
    severidad = models.CharField(max_length=3, choices=Severidad.choices, default=Severidad.LEVE)
    descripcion = models.TextField()
    diferencia = models.DecimalField(max_digits=12, decimal_places=2,
                                     help_text='Valor numérico de la diferencia detectada')
    resuelto = models.BooleanField(default=False)
    es_automatico = models.BooleanField(
        default=False,
        help_text='True si fue generado por la detección automática (HU-13), no registrado a mano',
    )
    detectado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='descuadres_detectados',
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    resuelto_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Descuadre'
        verbose_name_plural = 'Descuadres'
        ordering = ['resuelto', '-creado_en']

    def __str__(self):
        return f'{self.fecha} — {self.get_tipo_display()} ({self.get_severidad_display()})'


class CierreAnual(models.Model):
    anio = models.PositiveIntegerField(unique=True)
    cerrado = models.BooleanField(default=True)
    cerrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='cierres_realizados',
    )
    fecha_cierre = models.DateTimeField(auto_now_add=True)
    reabierto_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='cierres_reabiertos',
    )
    fecha_reapertura = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Cierre Anual'
        verbose_name_plural = 'Cierres Anuales'
        ordering = ['-anio']

    def __str__(self):
        estado = 'Cerrado' if self.cerrado else 'Reabierto'
        return f'{self.anio} — {estado}'