from django import forms
from django.forms import inlineformset_factory
from .models import Producto, Insumo, Produccion, ConsumoInsumo, CompraInsumo


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