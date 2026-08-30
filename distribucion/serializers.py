from rest_framework import serializers
from produccion.models import Producto
from .models import Cliente, PrecioPorCategoria, Planilla, Entrega, Averia, Credito


class ProductoSerializer(serializers.ModelSerializer):
    presentacion_display = serializers.CharField(source='get_presentacion_display', read_only=True)

    class Meta:
        model = Producto
        fields = ['id', 'nombre', 'presentacion', 'presentacion_display', 'unidad_medida']


class PrecioPorCategoriaSerializer(serializers.ModelSerializer):
    producto_nombre = serializers.CharField(source='producto.nombre', read_only=True)

    class Meta:
        model = PrecioPorCategoria
        fields = ['producto', 'producto_nombre', 'precio']


class ClienteConPreciosSerializer(serializers.ModelSerializer):
    precios = serializers.SerializerMethodField()

    class Meta:
        model = Cliente
        fields = ['id', 'nombre', 'telefono', 'categoria', 'precios']

    def get_precios(self, obj):
        qs = PrecioPorCategoria.objects.filter(categoria=obj.categoria).select_related('producto')
        return PrecioPorCategoriaSerializer(qs, many=True).data


class EntregaSerializer(serializers.ModelSerializer):
    subtotal = serializers.SerializerMethodField()
    cliente_nombre = serializers.CharField(source='cliente.nombre', read_only=True)
    producto_nombre = serializers.CharField(source='producto.nombre', read_only=True)

    class Meta:
        model = Entrega
        fields = [
            'id', 'planilla', 'cliente', 'cliente_nombre',
            'producto', 'producto_nombre', 'cantidad',
            'precio_unitario', 'modalidad_pago', 'devolucion',
            'subtotal', 'creado_en',
        ]
        read_only_fields = ['id', 'creado_en']

    def get_subtotal(self, obj):
        return float(obj.subtotal)

    def validate(self, data):
        cliente = data.get('cliente')
        producto = data.get('producto')
        if cliente and producto:
            try:
                precio = PrecioPorCategoria.objects.get(categoria=cliente.categoria, producto=producto)
            except PrecioPorCategoria.DoesNotExist:
                raise serializers.ValidationError(
                    f'No hay precio configurado para la categoría {cliente.get_categoria_display()} '
                    f'y el producto {producto.nombre}.'
                )
            data['precio_unitario'] = precio.precio
        return data

    def create(self, validated_data):
        entrega = super().create(validated_data)
        if entrega.modalidad_pago == Entrega.ModalidadPago.CREDITO:
            monto = entrega.subtotal
            Credito.objects.create(
                cliente=entrega.cliente,
                entrega=entrega,
                monto=monto,
                saldo_pendiente=monto,
            )
        return entrega


class AveriaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Averia
        fields = ['id', 'planilla', 'producto', 'cantidad', 'descripcion']
        read_only_fields = ['id']


class PlanillaSerializer(serializers.ModelSerializer):
    entregas = EntregaSerializer(many=True, read_only=True)
    averias = AveriaSerializer(many=True, read_only=True)
    distribuidor_nombre = serializers.SerializerMethodField()
    total_ventas = serializers.SerializerMethodField()

    class Meta:
        model = Planilla
        fields = [
            'id', 'fecha', 'distribuidor', 'distribuidor_nombre',
            'estado', 'entregas', 'averias', 'total_ventas', 'observaciones',
        ]

    def get_distribuidor_nombre(self, obj):
        return obj.distribuidor.get_full_name() or obj.distribuidor.username

    def get_total_ventas(self, obj):
        return float(sum(e.subtotal for e in obj.entregas.all()))
