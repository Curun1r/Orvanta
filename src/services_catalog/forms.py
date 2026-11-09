from django.utils.translation import gettext_lazy as _, pgettext_lazy
from django import forms

from config.form_ui import BootstrapFormMixin

from .models import Service, ServiceCategory


class ServiceCategoryForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = ServiceCategory
        fields = ['name', 'description']
        labels = {
            'name': _('Name'),
            'description': _('Description'),
        }
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': _('For example, consultations')}),
            'description': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': _('Short category description'),
            }),
        }


class ServiceForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Service
        fields = ['category', 'name', 'description', 'price', 'duration_minutes', 'is_active']
        labels = {
            'category': _('Category'),
            'name': _('Name'),
            'description': _('Description'),
            'price': _('Base price'),
            'duration_minutes': _('Duration, min'),
            'is_active': pgettext_lazy('service status', 'Active'),
        }
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': _('Service name')}),
            'description': forms.Textarea(attrs={
                'rows': 4,
                'placeholder': _('What the service includes'),
            }),
            'price': forms.NumberInput(attrs={
                'min': '0',
                'step': '0.01',
                'placeholder': '0.00',
            }),
            'duration_minutes': forms.NumberInput(attrs={
                'min': '1',
                'step': '1',
                'placeholder': '60',
            }),
        }

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].empty_label = _('Uncategorized')
        if organization is None:
            self.fields['category'].queryset = ServiceCategory.objects.none()
        else:
            self.fields['category'].queryset = ServiceCategory.objects.filter(
                organization=organization,
            ).order_by('name')


class ServiceFilterForm(forms.Form):
    query = forms.CharField(
        required=False,
        label=_('Search'),
        widget=forms.TextInput(attrs={'placeholder': _('Service name or description')}),
    )
    category = forms.ModelChoiceField(
        required=False,
        label=_('Category'),
        queryset=ServiceCategory.objects.none(),
        empty_label=_('All categories'),
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

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        if organization is None:
            self.fields['category'].queryset = ServiceCategory.objects.none()
        else:
            self.fields['category'].queryset = ServiceCategory.objects.filter(
                organization=organization,
            ).order_by('name')
