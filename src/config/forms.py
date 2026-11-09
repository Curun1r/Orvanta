from django.utils.translation import gettext_lazy as _
from django import forms

from appointments.models import AppointmentStatus
from config.form_ui import BootstrapFormMixin
from services_catalog.models import Service
from users.models import User, UserRole


class FinanceAnalyticsFilterForm(BootstrapFormMixin, forms.Form):
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
    service = forms.ModelChoiceField(
        required=False,
        label=_('Service'),
        queryset=Service.objects.none(),
        empty_label=_('All services'),
    )
    employee = forms.ModelChoiceField(
        required=False,
        label=_('Employee'),
        queryset=User.objects.none(),
        empty_label=_('All employees'),
    )
    status = forms.ChoiceField(
        required=False,
        label=_('Status'),
        choices=list(AppointmentStatus.choices),
    )

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['status'].initial = AppointmentStatus.COMPLETED

        if organization is None:
            return

        self.fields['service'].queryset = Service.objects.filter(
            organization=organization,
        ).order_by('name')
        self.fields['employee'].queryset = User.objects.filter(
            organization=organization,
            role=UserRole.EMPLOYEE,
        ).order_by('username')
