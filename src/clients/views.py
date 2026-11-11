from django.utils.translation import gettext as _
from django.contrib import messages
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from config.csv_export import (
    build_csv_response,
    format_csv_bool,
    format_csv_datetime,
)
from config.utils import filtered_paginated_response
from django.conf import settings
from users.decorators import (
    employee_manager_admin_required,
    manager_or_admin_required,
    organization_required,
)

from appointments.models import AppointmentStatus
from appointments.querysets import appointments_visible_to

from .forms import ClientFilterForm, ClientForm
from .models import Client

CLIENTS_PAGE_SIZE = settings.PAGINATION_PAGE_SIZE


def _organization_clients_queryset(user):
    if user.organization_id is None:
        return Client.objects.none()
    return Client.objects.filter(organization=user.organization)


def _filtered_clients_queryset(user, data):
    clients = _organization_clients_queryset(user)
    filter_form = ClientFilterForm(data or None)

    if filter_form.is_valid():
        query = filter_form.cleaned_data.get('query')
        is_active = filter_form.cleaned_data.get('is_active')

        if query:
            clients = clients.filter(
                Q(full_name__icontains=query) |
                Q(phone__icontains=query) |
                Q(email__icontains=query)
            )

        if is_active == 'true':
            clients = clients.filter(is_active=True)
        elif is_active == 'false':
            clients = clients.filter(is_active=False)

    return clients, filter_form


@employee_manager_admin_required
def client_list_view(request):
    clients, filter_form = _filtered_clients_queryset(request.user, request.GET)
    return filtered_paginated_response(
        request, clients, CLIENTS_PAGE_SIZE,
        'clients/client_list.html',
        extra_context={'filter_form': filter_form},
    )


@manager_or_admin_required
def client_export_csv_view(request):
    clients, _filter_form = _filtered_clients_queryset(request.user, request.GET)
    filename = f'clients_export_{timezone.localdate():%Y%m%d}.csv'
    headers = [
        'ID',
        _('Full name'),
        _('Phone'),
        'Email',
        _('Active'),
        _('Created at'),
        _('Updated at'),
    ]
    rows = (
        [
            client.pk,
            client.full_name,
            client.phone,
            client.email or '',
            format_csv_bool(client.is_active),
            format_csv_datetime(client.created_at),
            format_csv_datetime(client.updated_at),
        ]
        for client in clients
    )

    return build_csv_response(filename, headers, rows)


@manager_or_admin_required
@organization_required
def client_create_view(request):
    if request.method == 'POST':
        form = ClientForm(request.POST)
        if form.is_valid():
            client = form.save(commit=False)
            client.created_by = request.user
            client.organization = request.user.organization
            client.save()
            messages.success(request, _('Client created successfully.'))
            return redirect('client_list')
    else:
        form = ClientForm()

    return render(request, 'clients/client_form.html', {
        'form': form,
        'title': _('Add client'),
    })


@manager_or_admin_required
def client_update_view(request, pk):
    client = get_object_or_404(
        Client,
        pk=pk,
        organization=request.user.organization,
    )

    if request.method == 'POST':
        form = ClientForm(request.POST, instance=client)
        if form.is_valid():
            form.save()
            messages.success(request, _('Client details updated successfully.'))
            return redirect('client_list')
    else:
        form = ClientForm(instance=client)

    return render(request, 'clients/client_form.html', {
        'form': form,
        'title': _('Edit client'),
    })


@employee_manager_admin_required
def client_detail_view(request, pk):
    client = get_object_or_404(
        Client,
        pk=pk,
        organization=request.user.organization,
    )

    all_appointments = appointments_visible_to(request.user).filter(client=client)
    appointments = all_appointments.order_by('-appointment_date', '-start_time')

    # Фільтрація
    status_filter  = request.GET.get('status', '')
    date_from      = request.GET.get('date_from', '')
    date_to        = request.GET.get('date_to', '')

    if status_filter:
        appointments = appointments.filter(status=status_filter)
    if date_from:
        appointments = appointments.filter(appointment_date__gte=date_from)
    if date_to:
        appointments = appointments.filter(appointment_date__lte=date_to)

    # Статистика за всіма доступними записами клієнта, без фільтрів сторінки.
    total_count      = all_appointments.count()
    completed_count  = all_appointments.filter(status=AppointmentStatus.COMPLETED).count()
    total_spent_by_currency = [
        {'currency': item['service__currency'], 'amount': item['amount']}
        for item in all_appointments.filter(
        status=AppointmentStatus.COMPLETED,
        actual_price__isnull=False,
        ).values('service__currency').annotate(amount=Sum('actual_price')).order_by('service__currency')
    ]
    total_spent = total_spent_by_currency[0]['amount'] if len(total_spent_by_currency) == 1 else (None if total_spent_by_currency else 0)
    last_visit = (
        all_appointments
        .filter(status=AppointmentStatus.COMPLETED)
        .order_by('-appointment_date')
        .values_list('appointment_date', flat=True)
        .first()
    )

    status_choices = [('', _('All statuses'))] + list(AppointmentStatus.choices)

    return render(request, 'clients/client_detail.html', {
        'client':          client,
        'appointments':    appointments,
        'status_filter':   status_filter,
        'date_from':       date_from,
        'date_to':         date_to,
        'status_choices':  status_choices,
        'total_count':     total_count,
        'completed_count': completed_count,
        'total_spent':     total_spent,
        'total_spent_by_currency': total_spent_by_currency,
        'last_visit':      last_visit,
    })


@manager_or_admin_required
@require_POST
def client_toggle_active_view(request, pk):
    client = get_object_or_404(
        Client,
        pk=pk,
        organization=request.user.organization,
    )
    client.is_active = not client.is_active
    client.save(update_fields=['is_active', 'updated_at'])

    if client.is_active:
        messages.success(request, _('Client activated successfully.'))
    else:
        messages.success(request, _('Client deactivated successfully.'))

    return redirect('client_list')
