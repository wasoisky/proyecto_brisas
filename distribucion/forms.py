from django import forms
from .models import Cliente, PrecioPorCategoria, Planilla, Entrega, Averia


class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = ['nombre', 'telefono', 'direccion', 'categoria', 'autoriza_datos', 'activo']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control'}),
            'direccion': forms.TextInput(attrs={'class': 'form-control'}),
            'categoria': forms.Select(attrs={'class': 'form-select'}),
            'autoriza_datos': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class PrecioPorCategoriaForm(forms.ModelForm):
    class Meta:
        model = PrecioPorCategoria
        fields = ['categoria', 'producto', 'precio']
        widgets = {
            'categoria': forms.Select(attrs={'class': 'form-select'}),
            'producto': forms.Select(attrs={'class': 'form-select'}),
            'precio': forms.NumberInput(attrs={'class': 'form-control', 'step': '50', 'min': '0'}),
        }


class PlanillaForm(forms.ModelForm):
    class Meta:
        model = Planilla
        fields = ['fecha', 'distribuidor', 'observaciones']
        widgets = {
            'fecha': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'distribuidor': forms.Select(attrs={'class': 'form-select'}),
            'observaciones': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class EntregaForm(forms.ModelForm):
    class Meta:
        model = Entrega
        fields = ['cliente', 'producto', 'cantidad', 'precio_unitario', 'modalidad_pago', 'devolucion']
        widgets = {
            'cliente': forms.Select(attrs={'class': 'form-select'}),
            'producto': forms.Select(attrs={'class': 'form-select'}),
            'cantidad': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'precio_unitario': forms.NumberInput(attrs={'class': 'form-control', 'step': '50', 'min': '0'}),
            'modalidad_pago': forms.Select(attrs={'class': 'form-select'}),
            'devolucion': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
        }


class AveriaForm(forms.ModelForm):
    class Meta:
        model = Averia
        fields = ['producto', 'cantidad', 'descripcion']
        widgets = {
            'producto': forms.Select(attrs={'class': 'form-select'}),
            'cantidad': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }
