from django.db import models
from django.utils.translation import gettext_lazy as _


class Currency(models.TextChoices):
    UAH = 'UAH', _('Ukrainian hryvnia (UAH)')
    EUR = 'EUR', _('Euro (EUR)')
    USD = 'USD', _('US dollar (USD)')
