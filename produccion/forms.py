from django import forms
from django.forms import inlineformset_factory
from .models import Producto, Insumo, Produccion, ConsumoInsumo, CompraInsumo, RecetaProducto, Regalia


class ProductoForm(forms.ModelForm):
    class Meta:
        model = Producto
        fields = ['nombre', 'presentacion', 'unidad_medida', 'activo']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'presentacion': forms.Select(attrs={'class': 'form-select'}),
            'unidad_medida': forms.TextInput(attrs={'class': 'form-control'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class InsumoForm(forms.ModelForm):
    class Meta:
        model = Insumo
        fields = ['nombre', 'categoria', 'unidad_medida', 'stock_actual', 'stock_minimo', 'activo']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'categoria': forms.Select(attrs={'class': 'form-select'}),
            'unidad_medida': forms.TextInput(attrs={'class': 'form-control'}),
            'stock_actual': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'stock_minimo': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class ProduccionForm(forms.ModelForm):
    class Meta:
        model = Produccion
        fields = ['fecha', 'lote', 'producto', 'cantidad_producida', 'observaciones']
        widgets = {
            'fecha': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'lote': forms.TextInput(attrs={'class': 'form-control'}),
            'producto': forms.Select(attrs={'class': 'form-select'}),
            'cantidad_producida': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'observaciones': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class CompraInsumoForm(forms.ModelForm):
    class Meta:
        model = CompraInsumo
        fields = ['fecha', 'insumo', 'cantidad', 'precio_unitario', 'proveedor', 'factura']
        widgets = {
            'fecha': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'insumo': forms.Select(attrs={'class': 'form-select'}),
            'cantidad': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0.01'}),
            'precio_unitario': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'proveedor': forms.TextInput(attrs={'class': 'form-control'}),
            'factura': forms.TextInput(attrs={'class': 'form-control'}),
        }


class RegaliaForm(forms.ModelForm):
    class Meta:
        model = Regalia
        fields = ['fecha', 'producto', 'produccion', 'cantidad', 'destinatario', 'motivo', 'observaciones']
        widgets = {
            'fecha': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'producto': forms.Select(attrs={'class': 'form-select'}),
            'produccion': forms.Select(attrs={'class': 'form-select'}),
            'cantidad': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'destinatario': forms.TextInput(attrs={'class': 'form-control'}),
            'motivo': forms.Select(attrs={'class': 'form-select'}),
            'observaciones': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['produccion'].required = False
        self.fields['produccion'].queryset = Produccion.objects.order_by('-fecha')


RecetaProductoFormSet = inlineformset_factory(
    Producto,
    RecetaProducto,
    fields=['insumo', 'cantidad_por_unidad'],
    extra=1,
    can_delete=True,
    widgets={
        'insumo': forms.Select(attrs={'class': 'form-select form-select-sm'}),
        'cantidad_por_unidad': forms.NumberInput(attrs={
            'class': 'form-control form-control-sm', 'step': '0.0001', 'min': '0.0001'
        }),
    },
)

ConsumoInsumoFormSet = inlineformset_factory(
    Produccion,
    ConsumoInsumo,
    fields=['insumo', 'cantidad'],
    extra=2,
    can_delete=True,
    widgets={
        'insumo': forms.Select(attrs={'class': 'form-select form-select-sm'}),
        'cantidad': forms.NumberInput(attrs={
            'class': 'form-control form-control-sm', 'step': '0.01', 'min': '0.01'
        }),
    },
)