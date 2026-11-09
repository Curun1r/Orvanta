from django.contrib.auth.models import AbstractUser
from django.db import models


class UserRole(models.TextChoices):
    ADMIN = 'admin', 'Адміністратор'
    MANAGER = 'manager', 'Менеджер'
    EMPLOYEE = 'employee', 'Співробітник'


class Organization(models.Model):
    name = models.CharField(max_length=255, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    is_demo = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Організація'
        verbose_name_plural = 'Організації'

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
        verbose_name='Приховати підписи під заголовками',
    )

    class Meta:
        verbose_name = 'Користувач'
        verbose_name_plural = 'Користувачі'
        indexes = [
            models.Index(fields=['organization', 'role'], name='user_org_role_idx'),
            models.Index(fields=['organization', 'is_active'], name='user_org_active_idx'),
            models.Index(fields=['organization', 'username'], name='user_org_name_idx'),
            models.Index(fields=['organization', '-date_joined'], name='user_org_joined_idx'),
        ]

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"
