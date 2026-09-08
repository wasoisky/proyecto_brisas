from django.db import migrations

CATEGORIAS = [
    (1, 'Materia prima y tratamiento de agua'),
    (2, 'Envases y empaques'),
    (3, 'Tapas y sellado'),
    (4, 'Etiquetas e impresión'),
    (5, 'Químicos de limpieza y desinfección'),
    (6, 'Repuestos y mantenimiento'),
    (7, 'Elementos de protección personal'),
    (8, 'Papelería y administrativos'),
    (9, 'Otros'),
]

UNIDADES = [
    (1, 'unidad'),
    (2, 'millar'),
    (3, 'paquete'),
    (4, 'rollo'),
    (5, 'caja'),
    (6, 'bulto'),
    (7, 'kilogramo'),
    (8, 'gramo'),
    (9, 'litro'),
    (10, 'mililitro'),
    (11, 'metro'),
    (12, 'bolsa'),
    (13, 'paca'),
]


def poblar(apps, schema_editor):
    CategoriaInsumo = apps.get_model('produccion', 'CategoriaInsumo')
    UnidadMedida = apps.get_model('produccion', 'UnidadMedida')

    for orden, nombre in CATEGORIAS:
        CategoriaInsumo.objects.get_or_create(nombre=nombre, defaults={'orden': orden})

    for orden, nombre in UNIDADES:
        UnidadMedida.objects.get_or_create(nombre=nombre, defaults={'orden': orden})


def revertir(apps, schema_editor):
    CategoriaInsumo = apps.get_model('produccion', 'CategoriaInsumo')
    UnidadMedida = apps.get_model('produccion', 'UnidadMedida')
    CategoriaInsumo.objects.filter(nombre__in=[n for _, n in CATEGORIAS]).delete()
    UnidadMedida.objects.filter(nombre__in=[n for _, n in UNIDADES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('produccion', '0005_categoriainsumo_unidadmedida'),
    ]

    operations = [
        migrations.RunPython(poblar, revertir),
    ]
