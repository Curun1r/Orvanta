from django.utils.translation import gettext_lazy as _
from django.contrib.auth.models import AbstractUser
from django.db import models


class UserRole(models.TextChoices):
    ADMIN = 'admin', _('Administrator')
    MANAGER = 'manager', _('Manager')
    EMPLOYEE = 'employee', _('Employee')


class OrganizationTimeFormat(models.TextChoices):
    TWENTY_FOUR_HOUR = '24', _('24-hour (14:30)')
    TWELVE_HOUR = '12', _('12-hour (2:30 PM)')


class Organization(models.Model):
    name = models.CharField(max_length=255, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    is_demo = models.BooleanField(default=False)
    time_format = models.CharField(
        max_length=2,
        choices=OrganizationTimeFormat.choices,
        default=OrganizationTimeFormat.TWENTY_FOUR_HOUR,
        verbose_name=_('Time format'),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = _('Organization')
        verbose_name_plural = _('Organizations')

    def __str__(self):
        return self.name


class User(AbstractUser):
    phone = models.CharField(max_length=20, blank=True, null=True)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users',
    )
    role = models.CharField(
        max_length=20,
        choices=UserRole.choices,
        default=UserRole.EMPLOYEE
    )
    hide_section_subtitles = models.BooleanField(
        default=False,
        verbose_name=_('Hide section subtitles'),
    )

    class Meta:
        verbose_name = _('User')
        verbose_name_plural = _('Users')
        indexes = [
            models.Index(fields=['organization', 'role'], name='user_org_role_idx'),
            models.Index(fields=['organization', 'is_active'], name='user_org_active_idx'),
            models.Index(fields=['organization', 'username'], name='user_org_name_idx'),
            models.Index(fields=['organization', '-date_joined'], name='user_org_joined_idx'),
        ]

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"
