from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import Usuario


class UsuarioCreateForm(UserCreationForm):
    class Meta:
        model = Usuario
        fields = ['username', 'first_name', 'last_name', 'email', 'telefono', 'rol']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _bootstrap(self.fields)
        self.fields['first_name'].required = True
        self.fields['last_name'].required = True


class UsuarioUpdateForm(forms.ModelForm):
    class Meta:
        model = Usuario
        fields = ['first_name', 'last_name', 'email', 'telefono', 'rol', 'is_active']
        widgets = {
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _bootstrap(self.fields, skip=['is_active'])
        self.fields['first_name'].required = True
        self.fields['last_name'].required = True


class AdminPasswordResetForm(forms.Form):
    password1 = forms.CharField(
        label='Nueva contraseña',
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'autocomplete': 'new-password'}),
    )
    password2 = forms.CharField(
        label='Confirmar contraseña',
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'autocomplete': 'new-password'}),
    )

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get('password1')
        p2 = cleaned.get('password2')
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError('Las contraseñas no coinciden.')
        return cleaned


def _bootstrap(fields, skip=None):
    skip = skip or []
    for name, field in fields.items():
        if name in skip:
            continue
        widget = field.widget
        if isinstance(widget, (forms.TextInput, forms.EmailInput,
                                forms.PasswordInput, forms.NumberInput,
                                forms.URLInput, forms.Textarea)):
            widget.attrs.setdefault('class', 'form-control')
        elif isinstance(widget, forms.Select):
            widget.attrs.setdefault('class', 'form-select')
