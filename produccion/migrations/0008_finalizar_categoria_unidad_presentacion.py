import django.db.models.deletion
from django.db import migrations, models

# Producto.presentacion: código viejo -> código nuevo. 'BOT' se mantiene igual.
# Los dos productos "Paca ..." colapsan a un solo código PAC — la distinción
# con/sin tapa pasa a vivir en el nombre libre (decisión confirmada). El
# producto de prueba "agua botella" (también código viejo PST) se deja SIN
# tocar aquí a propósito: su presentación real todavía no está confirmada.
REMAPEO_PRESENTACION = {
    'PST': 'PAC',
    'PCT': 'PAC',
    'B5L': 'BIN',
    'B3C': 'BIN',
    'HIE': 'BIN',
}
NOMBRES_PENDIENTES = ['agua botella']


def remapear_presentacion(apps, schema_editor):
    Producto = apps.get_model('produccion', 'Producto')
    for producto in Producto.objects.exclude(nombre__in=NOMBRES_PENDIENTES):
        nuevo = REMAPEO_PRESENTACION.get(producto.presentacion)
        if nuevo:
            producto.presentacion = nuevo
            producto.save(update_fields=['presentacion'])


def revertir_presentacion(apps, schema_editor):
    Producto = apps.get_model('produccion', 'Producto')
    inverso = {
        'PAC': 'PST',  # aproximado: no se puede distinguir PST de PCT al revertir
        'BIN': 'B5L',  # aproximado: no se puede distinguir B5L/B3C/HIE al revertir
    }
    for producto in Producto.objects.exclude(nombre__in=NOMBRES_PENDIENTES):
        viejo = inverso.get(producto.presentacion)
        if viejo:
            producto.presentacion = viejo
            producto.save(update_fields=['presentacion'])


class Migration(migrations.Migration):

    dependencies = [
        ('produccion', '0007_bridge_categoria_unidad_producto'),
    ]

    operations = [
        migrations.RemoveField(model_name='insumo', name='categoria'),
        migrations.RemoveField(model_name='insumo', name='unidad_medida'),
        migrations.RemoveField(model_name='producto', name='unidad_medida'),

        migrations.RenameField(model_name='insumo', old_name='categoria_fk', new_name='categoria'),
        migrations.RenameField(model_name='insumo', old_name='unidad_medida_fk', new_name='unidad_medida'),
        migrations.RenameField(model_name='producto', old_name='unidad_medida_fk', new_name='unidad_medida'),

        migrations.RunPython(remapear_presentacion, revertir_presentacion),

        migrations.AlterField(
            model_name='insumo',
            name='categoria',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT, related_name='insumos',
                to='produccion.categoriainsumo',
                help_text='Ej: Tapas y sellado — tapas plásticas, anillos de sellado, cinta selladora',
            ),
        ),
        migrations.AlterField(
            model_name='insumo',
            name='unidad_medida',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT, related_name='insumos',
                to='produccion.unidadmedida',
                help_text='Ej: rollo, kilogramo, millar',
            ),
        ),
        migrations.AlterField(
            model_name='insumo',
            name='nombre',
            field=models.CharField(max_length=60, help_text='Ej: Tapas plásticas, Cinta selladora'),
        ),
        migrations.AlterField(
            model_name='insumo',
            name='stock_actual',
            field=models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text='Ej: 8.20'),
        ),
        migrations.AlterField(
            model_name='insumo',
            name='stock_minimo',
            field=models.DecimalField(
                max_digits=10, decimal_places=2, default=0,
                help_text='Cantidad mínima antes de generar alerta. Ej: 3',
            ),
        ),
        migrations.AlterField(
            model_name='producto',
            name='unidad_medida',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT, related_name='productos_unidad',
                to='produccion.unidadmedida',
                help_text='Unidad en que se cuenta el producto terminado (normalmente "unidad")',
            ),
        ),
        migrations.AlterField(
            model_name='producto',
            name='presentacion',
            field=models.CharField(
                max_length=3,
                choices=[
                    ('PAC', 'Paca'),
                    ('BIN', 'Bolsa individual'),
                    ('BOT', 'Botellón'),
                    ('CAJ', 'Caja'),
                    ('BUL', 'Bulto'),
                ],
                help_text='Forma de empaque del producto terminado',
            ),
        ),
        migrations.AlterField(
            model_name='producto',
            name='nombre',
            field=models.CharField(max_length=60, help_text='Ej: Agua sin tapa, Agua con tapa, Hielo'),
        ),
    ]
