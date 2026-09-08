import django.db.models.deletion
from decimal import Decimal
from django.db import migrations, models

# Insumo.categoria (código viejo) -> CategoriaInsumo.nombre (nuevo), salvo casos
# especiales resueltos por nombre de insumo (ver POR_NOMBRE_CATEGORIA).
CATEGORIA_POR_CODIGO = {
    'PST': 'Envases y empaques',
    'PCT': 'Envases y empaques',
    'REE': 'Envases y empaques',
    'TAP': 'Tapas y sellado',
    'CIN': 'Tapas y sellado',
    'OTR': 'Otros',
}
# Insumo "botella" quedó como OTR/litro en los datos reales, pero es un envase,
# no "Otro" ni se cuenta en litros — corrección confirmada con el usuario.
CATEGORIA_POR_NOMBRE = {
    'botella': 'Envases y empaques',
}
UNIDAD_POR_NOMBRE_INSUMO = {
    'botella': 'unidad',
}
# Insumo.unidad_medida (texto libre viejo) -> UnidadMedida.nombre (nuevo).
UNIDAD_POR_TEXTO = {
    'rollo': 'rollo',
    'litro': 'litro',
    'unidad': 'unidad',
    'kg': 'kilogramo',
}

# Producto.unidad_medida (texto libre viejo) -> UnidadMedida.nombre: coinciden
# 1:1 porque 'bolsa' y 'paca' se agregaron al catálogo en la migración 0006.

# Contenido conocido y confirmado para 5 de los 7 productos reales. Los 2
# restantes (Paca sin tapa, Paca con tapa) y "agua botella" (dato de prueba a
# corregir) quedan sin contenido hasta que se confirmen los números reales —
# no se inventan.
CONTENIDO_POR_NOMBRE = {
    'Botellón 20L': (Decimal('20'), 'litro', None),
    'Bolsa 5L':      (Decimal('5'), 'litro', None),
    'Bolsa 300ml':   (Decimal('300'), 'mililitro', 28),
    'Hielo':         (Decimal('12'), 'kilogramo', None),
}


def poblar(apps, schema_editor):
    Insumo = apps.get_model('produccion', 'Insumo')
    Producto = apps.get_model('produccion', 'Producto')
    CategoriaInsumo = apps.get_model('produccion', 'CategoriaInsumo')
    UnidadMedida = apps.get_model('produccion', 'UnidadMedida')

    categorias = {c.nombre: c for c in CategoriaInsumo.objects.all()}
    unidades = {u.nombre: u for u in UnidadMedida.objects.all()}

    for insumo in Insumo.objects.all():
        nombre_categoria = CATEGORIA_POR_NOMBRE.get(
            insumo.nombre, CATEGORIA_POR_CODIGO[insumo.categoria]
        )
        insumo.categoria_fk = categorias[nombre_categoria]

        nombre_unidad = UNIDAD_POR_NOMBRE_INSUMO.get(
            insumo.nombre, UNIDAD_POR_TEXTO[insumo.unidad_medida]
        )
        insumo.unidad_medida_fk = unidades[nombre_unidad]
        insumo.save(update_fields=['categoria_fk', 'unidad_medida_fk'])

    for producto in Producto.objects.all():
        producto.unidad_medida_fk = unidades[producto.unidad_medida]

        contenido = CONTENIDO_POR_NOMBRE.get(producto.nombre)
        if contenido:
            cantidad, nombre_unidad_contenido, unidades_empaque = contenido
            producto.contenido_cantidad = cantidad
            producto.contenido_unidad = unidades[nombre_unidad_contenido]
            producto.unidades_por_empaque = unidades_empaque

        producto.save(update_fields=[
            'unidad_medida_fk', 'contenido_cantidad', 'contenido_unidad', 'unidades_por_empaque',
        ])


def revertir(apps, schema_editor):
    # Las columnas puente se eliminan solas al revertir el AddField de esta
    # misma migración; no hace falta limpiar datos.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('produccion', '0006_poblar_catalogos'),
    ]

    operations = [
        migrations.AddField(
            model_name='insumo',
            name='categoria_fk',
            field=models.ForeignKey(
                null=True, on_delete=django.db.models.deletion.PROTECT,
                related_name='insumos', to='produccion.categoriainsumo',
            ),
        ),
        migrations.AddField(
            model_name='insumo',
            name='unidad_medida_fk',
            field=models.ForeignKey(
                null=True, on_delete=django.db.models.deletion.PROTECT,
                related_name='insumos', to='produccion.unidadmedida',
            ),
        ),
        migrations.AddField(
            model_name='producto',
            name='unidad_medida_fk',
            field=models.ForeignKey(
                null=True, on_delete=django.db.models.deletion.PROTECT,
                related_name='productos_unidad', to='produccion.unidadmedida',
            ),
        ),
        migrations.AddField(
            model_name='producto',
            name='contenido_cantidad',
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=8, null=True,
                help_text='Ej: 300 (junto con la unidad de contenido, ej. ml)',
            ),
        ),
        migrations.AddField(
            model_name='producto',
            name='contenido_unidad',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                related_name='productos_contenido', to='produccion.unidadmedida',
                help_text='Unidad del contenido individual (ej. ml, L, kg)',
            ),
        ),
        migrations.AddField(
            model_name='producto',
            name='unidades_por_empaque',
            field=models.PositiveIntegerField(
                blank=True, null=True,
                help_text='Ej: 20, 25, 28 — cuántas unidades individuales trae el empaque (opcional)',
            ),
        ),
        migrations.RunPython(poblar, revertir),
    ]
