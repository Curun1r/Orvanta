from django.utils.translation import gettext_lazy as _, pgettext_lazy
from django import forms

from config.form_ui import BootstrapFormMixin

from .models import Client


class ClientForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Client
        fields = ['full_name', 'phone', 'email', 'birth_date', 'notes', 'is_active']
        labels = {
            'full_name': _('Full name'),
            'phone': _('Phone'),
            'email': 'Email',
            'birth_date': _('Date of birth'),
            'notes': _('Notes'),
            'is_active': _('Active'),
        }
        widgets = {
            'full_name': forms.TextInput(attrs={'placeholder': _('For example, Alex Morgan')}),
            'phone': forms.TextInput(attrs={'placeholder': '+380XXXXXXXXX'}),
            'email': forms.EmailInput(attrs={'placeholder': 'client@example.com'}),
            'birth_date': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={
                'rows': 4,
                'placeholder': _('Additional client information'),
            }),
        }


class ClientFilterForm(forms.Form):
    query = forms.CharField(
        required=False,
        label=_('Search'),
        widget=forms.TextInput(attrs={'placeholder': _('Full name, phone or email')}),
    )
    is_active = forms.ChoiceField(
        required=False,
        label=_('Status'),
        choices=[
            ('', _('All')),
            ('true', pgettext_lazy('summary', 'Active')),
            ('false', pgettext_lazy('summary', 'Inactive')),
        ],
    )
