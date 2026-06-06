from datetime import date
from django import forms
from .models import MovimientoActivo


class MovimientoActivoForm(forms.ModelForm):
    class Meta:
        model = MovimientoActivo
        fields = [
            'fecha', 'momento', 'tipo_activo',
            'cantidad_en_planta_lleno', 'cantidad_en_planta_vacio',
            'cantidad_en_clientes', 'cantidad_baja',
            'observaciones',
        ]
        widgets = {
            'fecha': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'momento': forms.Select(attrs={'class': 'form-select'}),
            'tipo_activo': forms.Select(attrs={'class': 'form-select', 'id': 'id_tipo_activo'}),
            'cantidad_en_planta_lleno': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'cantidad_en_planta_vacio': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'cantidad_en_clientes': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'cantidad_baja': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'observaciones': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def clean(self):
        cleaned = super().clean()
        # Para canastillas el campo "vacíos en planta" no aplica — se fuerza a 0
        if cleaned.get('tipo_activo') == 'CAN':
            cleaned['cantidad_en_planta_vacio'] = 0
        return cleaned
