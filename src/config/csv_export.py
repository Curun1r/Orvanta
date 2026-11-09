from django.utils.translation import gettext as _
import csv

from django.http import HttpResponse
from django.utils import timezone


def build_csv_response(filename, headers, rows):
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    response.write('\ufeff')

    writer = csv.writer(response, delimiter=';')
    writer.writerow(headers)
    writer.writerows(rows)

    return response


def format_csv_bool(value):
    return _('Yes') if value else _('No')


def format_csv_date(value):
    if value is None:
        return ''
    return value.strftime('%Y-%m-%d')


def format_csv_time(value):
    if value is None:
        return ''
    return value.strftime('%H:%M')


def format_csv_datetime(value):
    if value is None:
        return ''
    return timezone.localtime(value).strftime('%Y-%m-%d %H:%M')
