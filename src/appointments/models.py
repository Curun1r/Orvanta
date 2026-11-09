from django.utils.translation import gettext_lazy as _
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from clients.models import Client
from services_catalog.models import Service
from users.models import Organization


class AppointmentStatus(models.TextChoices):
    PLANNED = 'planned', _('Planned')
    CONFIRMED = 'confirmed', _('Confirmed')
    COMPLETED = 'completed', _('Completed')
    CANCELLED = 'cancelled', _('Cancelled')


class Appointment(models.Model):
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='appointments')
    service = models.ForeignKey(Service, on_delete=models.PROTECT, related_name='appointments')
    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='employee_appointments',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_appointments',
    )
    appointment_date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    actual_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        verbose_name=_('Actual price'),
        help_text=_('May differ from the service base price.'),
    )
    status = models.CharField(
        max_length=20,
        choices=AppointmentStatus.choices,
        default=AppointmentStatus.PLANNED,
    )
    comment = models.TextField(blank=True)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='appointments',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-appointment_date', '-start_time']
        verbose_name = _('Appointment')
        verbose_name_plural = _('Appointments')
        indexes = [
            models.Index(
                fields=['organization', 'appointment_date', 'start_time'],
                name='appt_org_date_start_idx',
            ),
            models.Index(fields=['organization', 'status'], name='appt_org_status_idx'),
            models.Index(
                fields=[
                    'organization',
                    'employee',
                    'appointment_date',
                    'start_time',
                    'end_time',
                ],
                name='appt_org_emp_date_time_idx',
            ),
            models.Index(fields=['organization', 'service'], name='appt_org_service_idx'),
        ]

    def __str__(self):
        return f'{self.client.full_name} - {self.service.name} ({self.appointment_date})'


class AppointmentStatusHistory(models.Model):
    appointment = models.ForeignKey(
        Appointment,
        on_delete=models.CASCADE,
        related_name='status_history',
    )
    old_status = models.CharField(max_length=20, choices=AppointmentStatus.choices)
    new_status = models.CharField(max_length=20, choices=AppointmentStatus.choices)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='changed_appointment_statuses',
    )
    changed_at = models.DateTimeField(auto_now_add=True)
    comment = models.TextField(blank=True)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='appointment_status_history',
    )

    class Meta:
        ordering = ['-changed_at']
        verbose_name = _('Appointment status history')
        verbose_name_plural = _('Appointment status history')
        indexes = [
            models.Index(
                fields=['organization', '-changed_at'],
                name='appt_hist_org_changed_idx',
            ),
            models.Index(
                fields=['organization', 'appointment', '-changed_at'],
                name='appt_hist_org_appt_idx',
            ),
        ]

    def __str__(self):
        return f'{self.appointment_id}: {self.old_status} -> {self.new_status}'
