from django.utils.translation import gettext_lazy as _
from django.conf import settings
from django.db import models

from users.models import Organization


class AuditActionType(models.TextChoices):
    LOGIN = 'login', _('Log in')
    LOGOUT = 'logout', _('Log out')
    CREATE = 'create', _('Creation')
    UPDATE = 'update', _('Update')
    DELETE = 'delete', _('Deletion')
    CHANGE_STATUS = 'change_status', _('Status change')
    ASSIGN_ROLE = 'assign_role', _('Role assignment')


class AuditEntityType(models.TextChoices):
    USER = 'user', _('User')
    CLIENT = 'client', _('Client')
    SERVICE = 'service', _('Service')
    APPOINTMENT = 'appointment', _('Appointment')
    AUTH = 'auth', _('Authentication')


class AuditLog(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs',
    )
    action_type = models.CharField(max_length=30, choices=AuditActionType.choices)
    entity_type = models.CharField(max_length=30, choices=AuditEntityType.choices)
    entity_id = models.PositiveIntegerField(null=True, blank=True)
    description = models.TextField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = _('Audit entry')
        verbose_name_plural = _('Audit log')
        indexes = [
            models.Index(fields=['organization', '-created_at'], name='audit_org_created_idx'),
            models.Index(fields=['organization', 'user', '-created_at'], name='audit_org_user_idx'),
            models.Index(
                fields=['organization', 'action_type', '-created_at'],
                name='audit_org_action_idx',
            ),
            models.Index(
                fields=['organization', 'entity_type', '-created_at'],
                name='audit_org_entity_idx',
            ),
        ]

    def __str__(self):
        return f'{self.action_type} - {self.entity_type} - {self.created_at:%Y-%m-%d %H:%M:%S}'
