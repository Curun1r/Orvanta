from django.utils.translation import gettext_lazy as _
from django import forms

from clients.models import Client
from config.form_ui import BootstrapFormMixin
from services_catalog.models import Service
from users.models import User, UserRole

from .models import Appointment, AppointmentStatus
from .scheduling import validate_appointment_slot


class AppointmentForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Appointment
        fields = [
            'client',
            'service',
            'employee',
            'appointment_date',
            'start_time',
            'end_time',
            'actual_price',
            'status',
            'comment',
        ]
        labels = {
            'client': _('Client'),
            'service': _('Service'),
            'employee': _('Employee'),
            'appointment_date': _('Appointment date'),
            'start_time': _('Start time'),
            'end_time': _('End time'),
            'actual_price': _('Actual price'),
            'status': _('Status'),
            'comment': _('Comment'),
        }
        help_texts = {
            'actual_price': _('The actual price may differ from the service base price.'),
        }
        widgets = {
            'appointment_date': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
            'start_time': forms.TimeInput(attrs={'type': 'time'}),
            'end_time': forms.TimeInput(attrs={'type': 'time'}),
            'actual_price': forms.NumberInput(attrs={
                'min': '0',
                'step': '0.01',
                'placeholder': '0.00',
            }),
            'comment': forms.Textarea(attrs={
                'rows': 4,
                'placeholder': _('Additional appointment details'),
            }),
        }

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.organization = organization
        self.fields['client'].empty_label = _('Select a client')
        self.fields['service'].empty_label = _('Select a service')
        self.fields['employee'].empty_label = _('Select an employee')

        if organization is None:
            self.fields['client'].queryset = Client.objects.none()
            self.fields['service'].queryset = Service.objects.none()
            self.fields['employee'].queryset = User.objects.none()
        else:
            self.fields['client'].queryset = Client.objects.filter(
                organization=organization,
            ).order_by('full_name')
            self.fields['service'].queryset = Service.objects.filter(
                organization=organization,
            ).order_by('name')
            self.fields['employee'].queryset = User.objects.filter(
                role=UserRole.EMPLOYEE,
                is_active=True,
                organization=organization,
            ).order_by('username')

    def clean(self):
        cleaned_data = super().clean()
        client = cleaned_data.get('client')
        service = cleaned_data.get('service')
        employee = cleaned_data.get('employee')
        appointment_date = cleaned_data.get('appointment_date')
        start_time = cleaned_data.get('start_time')
        end_time = cleaned_data.get('end_time')
        status = cleaned_data.get('status')

        if self.organization:
            if client and client.organization_id != self.organization.id:
                raise forms.ValidationError(_('The selected client does not belong to your organization.'))
            if service and service.organization_id != self.organization.id:
                raise forms.ValidationError(_('The selected service does not belong to your organization.'))
            if employee and employee.organization_id != self.organization.id:
                raise forms.ValidationError(_('The selected employee does not belong to your organization.'))

        if start_time and end_time and start_time >= end_time:
            raise forms.ValidationError(
                _('The appointment end time must be later than the start time.')
            )

        validate_appointment_slot(
            organization_id=self.organization.pk if self.organization else None,
            employee_id=employee.pk if employee else None,
            appointment_date=appointment_date,
            start_time=start_time,
            end_time=end_time,
            status=status,
            exclude_pk=self.instance.pk,
        )

        return cleaned_data


class AppointmentActualPriceForm(forms.ModelForm):
    class Meta:
        model = Appointment
        fields = ['actual_price']
        labels = {
            'actual_price': _('Actual price'),
        }
        widgets = {
            'actual_price': forms.NumberInput(
                attrs={
                    'class': 'form-control form-control-sm',
                    'min': '0',
                    'step': '0.01',
                    'placeholder': '0.00',
                },
            ),
        }


class AppointmentFilterForm(forms.Form):
    search = forms.CharField(
        required=False,
        label=_('Search'),
        widget=forms.TextInput(attrs={
            'placeholder': _('Client, service or employee...'),
            'autocomplete': 'off',
        }),
    )
    appointment_date = forms.DateField(
        required=False,
        label=_('Date'),
        widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
    )
    status = forms.ChoiceField(
        required=False,
        label=_('Status'),
        choices=[('', _('All statuses'))] + list(AppointmentStatus.choices),
    )
    employee = forms.ModelChoiceField(
        required=False,
        label=_('Employee'),
        queryset=User.objects.none(),
        empty_label=_('All employees'),
    )

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        if organization is None:
            self.fields['employee'].queryset = User.objects.none()
        else:
            self.fields['employee'].queryset = User.objects.filter(
                role=UserRole.EMPLOYEE,
                is_active=True,
                organization=organization,
            ).order_by('username')
