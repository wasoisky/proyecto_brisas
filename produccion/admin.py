from django.contrib import admin
from .models import Producto, Insumo, Produccion, ConsumoInsumo, CompraInsumo, RecetaProducto, Regalia


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'presentacion', 'unidad_medida', 'activo')
    list_filter = ('activo', 'presentacion')


@admin.register(Insumo)
class InsumoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'categoria', 'stock_actual', 'stock_minimo', 'unidad_medida', 'alerta_stock', 'activo')
    list_filter = ('activo', 'categoria')

    @admin.display(boolean=True, description='Alerta stock')
    def alerta_stock(self, obj):
        return obj.alerta_stock


class ConsumoInsumoInline(admin.TabularInline):
    model = ConsumoInsumo
    extra = 1


@admin.register(Produccion)
class ProduccionAdmin(admin.ModelAdmin):
    list_display = ('fecha', 'lote', 'producto', 'cantidad_producida', 'registrado_por')
    list_filter = ('fecha', 'producto')
    search_fields = ('lote',)
    inlines = [ConsumoInsumoInline]


@admin.register(CompraInsumo)
class CompraInsumoAdmin(admin.ModelAdmin):
    list_display = ('fecha', 'insumo', 'cantidad', 'precio_unitario', 'proveedor', 'factura', 'registrado_por')
    list_filter = ('fecha', 'insumo')
    search_fields = ('factura', 'proveedor')


@admin.register(Regalia)
class RegaliaAdmin(admin.ModelAdmin):
    list_display = ('fecha', 'producto', 'cantidad', 'motivo', 'destinatario', 'registrado_por')
    list_filter = ('fecha', 'motivo', 'producto')
    search_fields = ('destinatario',)


class RecetaInline(admin.TabularInline):
    model = RecetaProducto
    extra = 1
    fields = ('insumo', 'cantidad_por_unidad')


# Agregar inline de receta al admin de Producto
ProductoAdmin.inlines = [RecetaInline]