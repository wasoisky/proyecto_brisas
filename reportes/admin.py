from django.contrib import admin
from .models import Descuadre


@admin.register(Descuadre)
class DescuadreAdmin(admin.ModelAdmin):
    list_display = ('fecha', 'tipo', 'severidad', 'diferencia', 'resuelto', 'detectado_por')
    list_filter = ('resuelto', 'severidad', 'tipo')
    search_fields = ('descripcion',)
    readonly_fields = ('creado_en', 'resuelto_en')