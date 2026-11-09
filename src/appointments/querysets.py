from users.models import UserRole

from .models import Appointment


def appointments_visible_to(user):
    """Apply the same organization and role boundaries to every appointment read."""
    appointments = Appointment.objects.select_related('client', 'service', 'employee')
    if not user.is_authenticated or user.organization_id is None:
        return appointments.none()

    appointments = appointments.filter(organization_id=user.organization_id)
    if user.role == UserRole.EMPLOYEE:
        return appointments.filter(employee=user)
    if user.role in (UserRole.ADMIN, UserRole.MANAGER):
        return appointments
    return appointments.none()
