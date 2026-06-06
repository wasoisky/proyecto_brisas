from django.contrib import admin
from .models import Cliente, PrecioPorCategoria, Planilla, Entrega, Averia, Credito


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'categoria', 'telefono', 'autoriza_datos', 'activo')
    list_filter = ('categoria', 'activo', 'autoriza_datos')
    search_fields = ('nombre', 'telefono')


@admin.register(PrecioPorCategoria)
class PrecioPorCategoriaAdmin(admin.ModelAdmin):
    list_display = ('categoria', 'producto', 'precio')
    list_filter = ('categoria',)


class EntregaInline(admin.TabularInline):
    model = Entrega
    extra = 1


class AveriaInline(admin.TabularInline):
    model = Averia
    extra = 0


@admin.register(Planilla)
class PlanillaAdmin(admin.ModelAdmin):
    list_display = ('fecha', 'distribuidor', 'estado', 'creado_en')
    list_filter = ('estado', 'fecha', 'distribuidor')
    inlines = [EntregaInline, AveriaInline]


@admin.register(Credito)
class CreditoAdmin(admin.ModelAdmin):
    list_display = ('cliente', 'monto', 'saldo_pendiente', 'pagado', 'fecha_creacion', 'fecha_pago')
    list_filter = ('pagado', 'fecha_creacion')
    search_fields = ('cliente__nombre',)
