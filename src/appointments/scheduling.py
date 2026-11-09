from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError

from users.models import Organization

from .models import Appointment, AppointmentStatus


APPOINTMENT_CONFLICT_MESSAGE = (
    _('This employee already has an appointment during the selected time slot.')
)


def lock_organization_schedule(organization_id):
    """Serialize booking changes; call inside transaction.atomic(), before reading."""
    # NO KEY UPDATE still serializes bookings while allowing foreign-key references.
    Organization.objects.select_for_update(no_key=True).get(pk=organization_id)


def validate_appointment_slot(
    *, organization_id, employee_id, appointment_date, start_time, end_time,
    status, exclude_pk=None,
):
    if status == AppointmentStatus.CANCELLED or not all((
        organization_id, employee_id, appointment_date, start_time, end_time,
    )):
        return

    overlapping = Appointment.objects.filter(
        organization_id=organization_id,
        employee_id=employee_id,
        appointment_date=appointment_date,
        start_time__lt=end_time,
        end_time__gt=start_time,
    ).exclude(status=AppointmentStatus.CANCELLED)
    if exclude_pk is not None:
        overlapping = overlapping.exclude(pk=exclude_pk)
    if overlapping.exists():
        raise ValidationError(APPOINTMENT_CONFLICT_MESSAGE)
