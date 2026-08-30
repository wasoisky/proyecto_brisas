from django.contrib import admin
from .models import ActivoRetornable, BajaActivo, MovimientoActivo


@admin.register(ActivoRetornable)
class ActivoRetornableAdmin(admin.ModelAdmin):
    list_display = ('tipo', 'estado', 'activo')
    list_filter = ('tipo', 'estado', 'activo')


@admin.register(MovimientoActivo)
class MovimientoActivoAdmin(admin.ModelAdmin):
    list_display = ('fecha', 'momento', 'tipo_activo', 'cantidad_en_planta_lleno',
                    'cantidad_en_planta_vacio', 'cantidad_en_clientes', 'cantidad_baja', 'total')
    list_filter = ('fecha', 'momento', 'tipo_activo')
    readonly_fields = ('creado_en',)

    @admin.display(description='Total')
    def total(self, obj):
        return obj.total


@admin.register(BajaActivo)
class BajaActivoAdmin(admin.ModelAdmin):
    list_display = ('movimiento', 'cantidad', 'motivo', 'registrado_por', 'creado_en')
    list_filter = ('motivo',)
    readonly_fields = ('creado_en',)