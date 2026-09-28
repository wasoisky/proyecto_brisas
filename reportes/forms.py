from datetime import date
from django import forms

from config.widgets import FechaInput
from .models import Descuadre


class DescuadreForm(forms.ModelForm):
    class Meta:
        model = Descuadre
        fields = ['fecha', 'tipo', 'severidad', 'descripcion', 'diferencia']
        widgets = {
            'fecha': FechaInput(attrs={'class': 'form-control'}),
            'tipo': forms.Select(attrs={'class': 'form-select'}),
            'severidad': forms.Select(attrs={'class': 'form-select'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'diferencia': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['fecha'].initial = date.today()


class FiltroVentasForm(forms.Form):
    fecha_desde = forms.DateField(
        required=False,
        widget=FechaInput(attrs={'class': 'form-control form-control-sm'}),
    )
    fecha_hasta = forms.DateField(
        required=False,
        widget=FechaInput(attrs={'class': 'form-control form-control-sm'}),
    )
    distribuidor = forms.ChoiceField(
        required=False,
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'}),
    )

    def __init__(self, distribuidores, *args, **kwargs):
        super().__init__(*args, **kwargs)
        opciones = [('', 'Todos')]
        opciones += [(u.pk, u.get_full_name() or u.username) for u in distribuidores]
        self.fields['distribuidor'].choices = opciones
