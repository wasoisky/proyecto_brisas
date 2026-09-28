from django import forms


class FechaInput(forms.DateInput):
    """<input type="date"> con value en ISO (yyyy-mm-dd).

    Un input type=date solo acepta ese formato; con el formato regional es-co
    (d/m/Y) el navegador ignora el value y el campo aparece vacío.
    """
    input_type = 'date'

    def __init__(self, attrs=None, format='%Y-%m-%d'):
        super().__init__(attrs=attrs, format=format)
