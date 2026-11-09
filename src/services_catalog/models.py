from django.utils.translation import gettext_lazy as _
from django.db import models

from users.models import Organization


class ServiceCategory(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='service_categories',
    )

    class Meta:
        ordering = ['name']
        verbose_name = _('Service category')
        verbose_name_plural = _('Service categories')
        indexes = [
            models.Index(fields=['organization', 'name'], name='svc_cat_org_name_idx'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['organization', 'name'],
                name='unique_service_category_per_org',
            ),
        ]

    def __str__(self):
        return self.name


class Service(models.Model):
    category = models.ForeignKey(
        ServiceCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='services',
    )
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    duration_minutes = models.PositiveIntegerField()
    is_active = models.BooleanField(default=True)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='services',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = _('Service')
        verbose_name_plural = _('Services')
        indexes = [
            models.Index(fields=['organization', 'is_active'], name='svc_org_active_idx'),
            models.Index(fields=['organization', 'category'], name='svc_org_category_idx'),
            models.Index(fields=['organization', 'name'], name='svc_org_name_idx'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['organization', 'category', 'name'],
                name='unique_service_per_org_category',
            ),
        ]

    def __str__(self):
        return self.name
