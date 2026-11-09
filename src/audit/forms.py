from django.utils.translation import gettext_lazy as _
from django import forms

from users.models import User

from .models import AuditActionType, AuditEntityType


class AuditLogFilterForm(forms.Form):
    user = forms.ModelChoiceField(
        required=False,
        label=_('User'),
        queryset=User.objects.none(),
        empty_label=_('All users'),
    )
    action_type = forms.ChoiceField(
        required=False,
        label=_('Action type'),
        choices=[('', _('All actions'))] + list(AuditActionType.choices),
    )
    entity_type = forms.ChoiceField(
        required=False,
        label=_('Entity type'),
        choices=[('', _('All entities'))] + list(AuditEntityType.choices),
    )
    date_from = forms.DateField(
        required=False,
        label=_('Date from'),
        widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
    )
    date_to = forms.DateField(
        required=False,
        label=_('Date to'),
        widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
    )

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        if organization is None:
            self.fields['user'].queryset = User.objects.none()
        else:
            self.fields['user'].queryset = User.objects.filter(
                organization=organization,
            ).order_by('username')
