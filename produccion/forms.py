from django import forms
from django.forms import inlineformset_factory
from .models import (
    Producto, Insumo, Produccion, ConsumoInsumo, CompraInsumo, RecetaProducto, Regalia,
    CategoriaInsumo, UnidadMedida,
)

# Unidades válidas para "contenido" de un producto (volumen o masa) — de la
# lista completa de UnidadMedida, no tiene sentido que el contenido de una
# botella se exprese en "rollo" o "caja".
UNIDADES_CONTENIDO = ['litro', 'mililitro', 'gramo', 'kilogramo']


class ProductoForm(forms.ModelForm):
    class Meta:
        model = Producto
        fields = [
            'nombre', 'presentacion', 'contenido_cantidad', 'contenido_unidad',
            'unidades_por_empaque', 'unidad_medida', 'activo',
        ]
        widgets = {
            'nombre': forms.TextInput(attrs={
                'class': 'form-control', 'placeholder': 'Ej: Agua sin tapa',
            }),
            'presentacion': forms.Select(attrs={'class': 'form-select'}),
            'contenido_cantidad': forms.NumberInput(attrs={
                'class': 'form-control', 'step': '0.01', 'min': '0.01', 'placeholder': 'Ej: 300',
            }),
            'contenido_unidad': forms.Select(attrs={'class': 'form-select'}),
            'unidades_por_empaque': forms.NumberInput(attrs={
                'class': 'form-control', 'min': '1', 'placeholder': 'Ej: 20 (opcional)',
            }),
            'unidad_medida': forms.Select(attrs={'class': 'form-select'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['contenido_unidad'].queryset = UnidadMedida.objects.filter(
            activo=True, nombre__in=UNIDADES_CONTENIDO,
        ).order_by('orden')
        self.fields['contenido_unidad'].empty_label = 'Selecciona la unidad de contenido…'
        self.fields['unidad_medida'].queryset = UnidadMedida.objects.filter(activo=True).order_by('orden')
        self.fields['unidad_medida'].empty_label = 'Selecciona una unidad…'


class InsumoForm(forms.ModelForm):
    class Meta:
        model = Insumo
        fields = ['nombre', 'categoria', 'unidad_medida', 'stock_actual', 'stock_minimo', 'activo']
        widgets = {
            'nombre': forms.TextInput(attrs={
                'class': 'form-control', 'placeholder': 'Ej: Tapas plásticas, Cinta selladora',
            }),
            'categoria': forms.Select(attrs={'class': 'form-select'}),
            'unidad_medida': forms.Select(attrs={'class': 'form-select'}),
            'stock_actual': forms.NumberInput(attrs={
                'class': 'form-control', 'step': '0.01', 'placeholder': 'Ej: 8.20',
            }),
            'stock_minimo': forms.NumberInput(attrs={
                'class': 'form-control', 'step': '0.01', 'placeholder': 'Ej: 3',
            }),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['categoria'].queryset = CategoriaInsumo.objects.filter(activo=True).order_by('orden')
        self.fields['categoria'].empty_label = 'Selecciona una categoría…'
        self.fields['unidad_medida'].queryset = UnidadMedida.objects.filter(activo=True).order_by('orden')
        self.fields['unidad_medida'].empty_label = 'Selecciona una unidad…'

    def clean(self):
        cleaned_data = super().clean()
        nueva_unidad = cleaned_data.get('unidad_medida')
        if self.instance.pk and nueva_unidad and nueva_unidad != self.instance.unidad_medida:
            tiene_movimientos = (
                self.instance.consumos.exists() or self.instance.recetas.exists()
            )
            if tiene_movimientos:
                self.add_error(
                    'unidad_medida',
                    'No se puede cambiar la unidad de este insumo: ya tiene consumos de '
                    'producción o recetas registrados con la unidad actual. Corrige o elimina '
                    'esos registros primero, o crea un insumo nuevo con la unidad correcta.',
                )
        return cleaned_data


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


def _label_insumo_con_unidad(obj):
    return f'{obj.nombre} ({obj.unidad_medida})'


class RecetaProductoForm(forms.ModelForm):
    class Meta:
        model = RecetaProducto
        fields = ['insumo', 'cantidad_por_unidad']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['insumo'].label_from_instance = _label_insumo_con_unidad


class ConsumoInsumoForm(forms.ModelForm):
    class Meta:
        model = ConsumoInsumo
        fields = ['insumo', 'cantidad']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['insumo'].label_from_instance = _label_insumo_con_unidad


RecetaProductoFormSet = inlineformset_factory(
    Producto,
    RecetaProducto,
    form=RecetaProductoForm,
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
    form=ConsumoInsumoForm,
    extra=2,
    can_delete=True,
    widgets={
        'insumo': forms.Select(attrs={'class': 'form-select form-select-sm'}),
        'cantidad': forms.NumberInput(attrs={
            'class': 'form-control form-control-sm', 'step': '0.01', 'min': '0.01'
        }),
    },
)
