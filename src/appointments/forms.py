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
            'client': 'Клієнт',
            'service': 'Послуга',
            'employee': 'Співробітник',
            'appointment_date': 'Дата запису',
            'start_time': 'Час початку',
            'end_time': 'Час завершення',
            'actual_price': 'Фактична вартість',
            'status': 'Статус',
            'comment': 'Коментар',
        }
        help_texts = {
            'actual_price': 'Фактична вартість може відрізнятися від базової вартості послуги.',
        }
        widgets = {
            'appointment_date': forms.DateInput(attrs={'type': 'date'}),
            'start_time': forms.TimeInput(attrs={'type': 'time'}),
            'end_time': forms.TimeInput(attrs={'type': 'time'}),
            'actual_price': forms.NumberInput(attrs={
                'min': '0',
                'step': '0.01',
                'placeholder': '0.00',
            }),
            'comment': forms.Textarea(attrs={
                'rows': 4,
                'placeholder': 'Додаткові деталі запису',
            }),
        }

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.organization = organization
        self.fields['client'].empty_label = 'Оберіть клієнта'
        self.fields['service'].empty_label = 'Оберіть послугу'
        self.fields['employee'].empty_label = 'Оберіть співробітника'

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
                raise forms.ValidationError('Обраний клієнт не належить вашій організації.')
            if service and service.organization_id != self.organization.id:
                raise forms.ValidationError('Обрана послуга не належить вашій організації.')
            if employee and employee.organization_id != self.organization.id:
                raise forms.ValidationError('Обраний співробітник не належить вашій організації.')

        if start_time and end_time and start_time >= end_time:
            raise forms.ValidationError(
                'Час завершення запису повинен бути пізнішим за час початку.'
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
            'actual_price': 'Фактична вартість',
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
        label='Пошук',
        widget=forms.TextInput(attrs={
            'placeholder': 'Клієнт, послуга або співробітник...',
            'autocomplete': 'off',
        }),
    )
    appointment_date = forms.DateField(
        required=False,
        label='Дата',
        widget=forms.DateInput(attrs={'type': 'date'}),
    )
    status = forms.ChoiceField(
        required=False,
        label='Статус',
        choices=[('', 'Усі статуси')] + list(AppointmentStatus.choices),
    )
    employee = forms.ModelChoiceField(
        required=False,
        label='Співробітник',
        queryset=User.objects.none(),
        empty_label='Усі співробітники',
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
