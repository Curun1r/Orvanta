from datetime import datetime, time

from django import template
from django.utils import formats
from django.utils.timezone import template_localtime

from users.models import OrganizationTimeFormat


register = template.Library()


def _clock_pattern(preference):
    value = getattr(preference, 'time_format', preference)
    return 'g:i A' if value == OrganizationTimeFormat.TWELVE_HOUR else 'H:i'


@register.filter
def workspace_time(value, preference=OrganizationTimeFormat.TWENTY_FOUR_HOUR):
    if not isinstance(value, (datetime, time)):
        return ''
    return formats.time_format(template_localtime(value), _clock_pattern(preference))


@register.filter
def workspace_datetime(value, preference=OrganizationTimeFormat.TWENTY_FOUR_HOUR):
    if not isinstance(value, datetime):
        return ''
    local_value = template_localtime(value)
    date = formats.date_format(local_value, 'SHORT_DATE_FORMAT')
    clock = formats.time_format(local_value, _clock_pattern(preference))
    return f'{date} {clock}'
