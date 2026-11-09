from django.utils.translation import gettext_lazy as _
from django.apps import AppConfig


class AuditConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "audit"
    verbose_name = _('Audit')

    def ready(self):
        from django.db.models.signals import post_delete, post_save

        from appointments.models import Appointment
        from clients.models import Client
        from services_catalog.models import Service
        from users.models import User

        from .models import AuditEntityType
        from .signals import _TRACKED_MODELS, log_model_delete, log_model_save
        import audit.signals  # noqa: F401 — реєструє login/logout receivers

        _TRACKED_MODELS.update({
            Client: AuditEntityType.CLIENT,
            Service: AuditEntityType.SERVICE,
            Appointment: AuditEntityType.APPOINTMENT,
            User: AuditEntityType.USER,
        })

        for model in _TRACKED_MODELS:
            post_save.connect(log_model_save, sender=model)
            post_delete.connect(log_model_delete, sender=model)
