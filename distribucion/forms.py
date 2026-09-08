from django import forms
from .models import Cliente, PrecioPorCategoria, Planilla, Entrega, Averia


class ClienteForm(forms.ModelForm):
    # BooleanField.formfield() del modelo siempre genera required=False (un
    # checkbox "required" significa "debe estar marcado", no "debe tener un
    # valor"), sin importar blank=False. Se declara explícito para exigir el
    # consentimiento de la Ley 1581/2012 en el formulario.
    autoriza_datos = forms.BooleanField(
        required=True,
        label=Cliente._meta.get_field('autoriza_datos').verbose_name,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )

    class Meta:
        model = Cliente
        fields = ['nombre', 'telefono', 'direccion', 'categoria', 'autoriza_datos', 'activo']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control'}),
            'direccion': forms.TextInput(attrs={'class': 'form-control'}),
            'categoria': forms.Select(attrs={'class': 'form-select'}),
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

    def clean(self):
        cleaned_data = super().clean()
        cliente = cleaned_data.get('cliente')
        producto = cleaned_data.get('producto')
        if cliente and producto:
            try:
                precio = PrecioPorCategoria.objects.get(categoria=cliente.categoria, producto=producto)
            except PrecioPorCategoria.DoesNotExist:
                raise forms.ValidationError(
                    f'No hay precio configurado para la categoría {cliente.get_categoria_display()} '
                    f'y el producto {producto.nombre}.'
                )
            cleaned_data['precio_unitario'] = precio.precio
        return cleaned_data


class AveriaForm(forms.ModelForm):
    class Meta:
        model = Averia
        fields = ['producto', 'cantidad', 'descripcion']
        widgets = {
            'producto': forms.Select(attrs={'class': 'form-select'}),
            'cantidad': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }
