from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('produccion', '0004_regalia'),
    ]

    operations = [
        migrations.CreateModel(
            name='CategoriaInsumo',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre', models.CharField(max_length=60, unique=True)),
                ('descripcion', models.CharField(blank=True, max_length=200)),
                ('activo', models.BooleanField(default=True)),
                ('orden', models.PositiveSmallIntegerField(default=0)),
            ],
            options={
                'verbose_name': 'Categoría de Insumo',
                'verbose_name_plural': 'Categorías de Insumo',
                'ordering': ['orden', 'nombre'],
            },
        ),
        migrations.CreateModel(
            name='UnidadMedida',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre', models.CharField(max_length=40, unique=True)),
                ('descripcion', models.CharField(blank=True, max_length=200)),
                ('activo', models.BooleanField(default=True)),
                ('orden', models.PositiveSmallIntegerField(default=0)),
            ],
            options={
                'verbose_name': 'Unidad de Medida',
                'verbose_name_plural': 'Unidades de Medida',
                'ordering': ['orden', 'nombre'],
            },
        ),
    ]
