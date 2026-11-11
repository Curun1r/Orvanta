from django.utils.translation import gettext as _
import csv
import json
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Case, Count, Exists, IntegerField, Max, Min, OuterRef, Sum, When
from django.http import HttpResponse, JsonResponse
from django.core.paginator import Paginator
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone

from appointments.models import Appointment, AppointmentStatus, AppointmentStatusHistory
from appointments.querysets import appointments_visible_to
from audit.models import AuditLog, AuditActionType, AuditEntityType
from clients.models import Client
from config.csv_export import format_csv_date
from config.forms import FinanceAnalyticsFilterForm, default_currency_for
from services_catalog.models import Service, ServiceCategory
from users.decorators import admin_required, manager_or_admin_required
from users.models import User, UserRole


FINANCE_DETAIL_PAGE_SIZE = 25


def get_onboarding_status(user):
    organization = getattr(user, 'organization', None)

    if user.role != UserRole.ADMIN or organization is None:
        return None

    # Один запит замість 5 окремих EXISTS
    from users.models import Organization
    onboarding_flags = (
        Organization.objects.filter(pk=organization.pk)
        .annotate(
            has_service_category=Exists(
                ServiceCategory.objects.filter(organization=OuterRef('pk')),
            ),
            has_service=Exists(
                Service.objects.filter(organization=OuterRef('pk'), is_active=True),
            ),
            has_employee=Exists(
                User.objects.filter(
                    organization=OuterRef('pk'),
                    role=UserRole.EMPLOYEE,
                    is_active=True,
                ),
            ),
            has_client=Exists(
                Client.objects.filter(organization=OuterRef('pk'), is_active=True),
            ),
            has_appointment=Exists(
                Appointment.objects.filter(organization=OuterRef('pk')),
            ),
        )
        .values(
            'has_service_category',
            'has_service',
            'has_employee',
            'has_client',
            'has_appointment',
        )
        .first()
    )

    has_service_category = onboarding_flags['has_service_category']
    has_service          = onboarding_flags['has_service']
    has_employee         = onboarding_flags['has_employee']
    has_client           = onboarding_flags['has_client']
    has_appointment      = onboarding_flags['has_appointment']

    steps = [
        {
            'key': 'service_category',
            'label': _('Create your first service category'),
            'is_done': has_service_category,
            'url': reverse('category_create'),
            'action_label': _('Create category'),
        },
        {
            'key': 'service',
            'label': _('Create your first service'),
            'is_done': has_service,
            'url': reverse('service_create'),
            'action_label': _('Create service'),
        },
        {
            'key': 'employee',
            'label': _('Add an employee'),
            'is_done': has_employee,
            'url': reverse('user_create'),
            'action_label': _('Add employee'),
        },
        {
            'key': 'client',
            'label': _('Add a client'),
            'is_done': has_client,
            'url': reverse('client_create'),
            'action_label': _('Add client'),
        },
        {
            'key': 'appointment',
            'label': _('Create your first appointment'),
            'is_done': has_appointment,
            'url': reverse('appointment_create'),
            'action_label': _('Create appointment'),
        },
    ]

    return {
        'steps': steps,
        'is_complete': all(step['is_done'] for step in steps),
    }


def get_dashboard_analytics(user):
    user_organization = user.organization

    appointments = appointments_visible_to(user)

    raw_status_counts = (
        appointments.values('status')
        .annotate(total=Count('id'))
        .order_by('status')
    )

    status_map = dict(Appointment._meta.get_field('status').choices)
    status_class_map = {
        AppointmentStatus.PLANNED: 'planned',
        AppointmentStatus.CONFIRMED: 'confirmed',
        AppointmentStatus.COMPLETED: 'completed',
        AppointmentStatus.CANCELLED: 'cancelled',
    }
    # Один запит замість 9 окремих COUNT/aggregate
    stats = appointments.aggregate(
        total=Count('id'),
        completed=Count(Case(When(status=AppointmentStatus.COMPLETED, then=1), output_field=IntegerField())),
        cancelled=Count(Case(When(status=AppointmentStatus.CANCELLED, then=1), output_field=IntegerField())),
        planned=Count(Case(When(status=AppointmentStatus.PLANNED, then=1), output_field=IntegerField())),
        confirmed=Count(Case(When(status=AppointmentStatus.CONFIRMED, then=1), output_field=IntegerField())),
        completed_without_price=Count(Case(
            When(status=AppointmentStatus.COMPLETED, actual_price__isnull=True, then=1),
            output_field=IntegerField(),
        )),
        revenue_count=Count(Case(
            When(status=AppointmentStatus.COMPLETED, actual_price__isnull=False, then=1),
            output_field=IntegerField(),
        )),
    )

    appointments_total = stats['total']
    status_counts = [
        {
            'key': item['status'],
            'status': status_map.get(item['status'], item['status']),
            'total': item['total'],
            'percentage': round((item['total'] / appointments_total) * 100) if appointments_total else 0,
            'css_class': status_class_map.get(item['status'], 'default'),
        }
        for item in raw_status_counts
    ]

    popular_services = list(
        appointments.values('service__name')
        .annotate(total=Count('id'))
        .order_by('-total', 'service__name')[:5]
    )

    employee_workload = list(
        appointments.values('employee__username')
        .annotate(total=Count('id'))
        .order_by('-total', 'employee__username')[:5]
    )
    if employee_workload:
        max_workload = employee_workload[0]['total']
        for item in employee_workload:
            item['pct'] = round(item['total'] / max_workload * 100) if max_workload else 0
    else:
        max_workload = 0

    revenue_by_currency = [
        {
            'currency': row['service__currency'],
            'total_revenue': _decimal_or_zero(row['total_revenue']),
            'average_check': _decimal_or_zero(row['average_check']),
            'revenue_appointments_count': row['count'],
        }
        for row in appointments.filter(
            status=AppointmentStatus.COMPLETED, actual_price__isnull=False,
        ).values('service__currency').annotate(
            total_revenue=Sum('actual_price'), average_check=Avg('actual_price'), count=Count('id'),
        ).order_by('service__currency')
    ]
    # Preserve scalar API values for a single currency, never add unlike units.
    single_revenue = revenue_by_currency[0] if len(revenue_by_currency) == 1 else None
    mixed_currencies = len(revenue_by_currency) > 1
    total_revenue = single_revenue['total_revenue'] if single_revenue else (None if mixed_currencies else Decimal('0.00'))
    average_check = single_revenue['average_check'] if single_revenue else (None if mixed_currencies else Decimal('0.00'))
    currency = single_revenue['currency'] if single_revenue else (None if mixed_currencies else default_currency_for(user_organization))

    # Один запит замість 4 окремих COUNT для клієнтів та послуг
    client_stats = Client.objects.filter(organization=user_organization).aggregate(
        total=Count('id'),
        active=Count(Case(When(is_active=True, then=1), output_field=IntegerField())),
    )
    service_stats = Service.objects.filter(organization=user_organization).aggregate(
        total=Count('id'),
        active=Count(Case(When(is_active=True, then=1), output_field=IntegerField())),
    )

    return {
        'appointments_queryset': appointments,
        'clients_count': client_stats['total'],
        'active_clients_count': client_stats['active'],
        'services_count': service_stats['total'],
        'active_services_count': service_stats['active'],
        'appointments_count': appointments_total,
        'employees_count': User.objects.filter(
            role=UserRole.EMPLOYEE,
            organization=user_organization,
        ).count(),
        'completed_count': stats['completed'],
        'cancelled_count': stats['cancelled'],
        'planned_count': stats['planned'],
        'confirmed_count': stats['confirmed'],
        'completed_without_price_count': stats['completed_without_price'],
        'total_revenue': total_revenue,
        'average_check': average_check,
        'currency': currency,
        'revenue_by_currency': revenue_by_currency,
        'revenue_appointments_count': stats['revenue_count'],
        'status_counts': status_counts,
        'popular_services': popular_services,
        'employee_workload': employee_workload,
    }


def _decimal_or_zero(value):
    return (value or Decimal('0.00')).quantize(Decimal('0.01'))


def _month_revenue(base_queryset, year, month):
    import calendar
    last_day = calendar.monthrange(year, month)[1]
    from datetime import date
    qs = base_queryset.filter(
        appointment_date__gte=date(year, month, 1),
        appointment_date__lte=date(year, month, last_day),
        actual_price__isnull=False,
        status=AppointmentStatus.COMPLETED,
    )
    totals = qs.aggregate(
        total_revenue=Sum('actual_price'),
        average_check=Avg('actual_price'),
        count=Count('id'),
    )
    return {
        'total_revenue': _decimal_or_zero(totals['total_revenue']),
        'average_check': _decimal_or_zero(totals['average_check']),
        'count': totals['count'] or 0,
    }


def _pct_change(current, previous):
    # Якщо попереднє значення нульове — відсоткову зміну неможливо обчислити
    if previous == 0:
        return None
    change = ((current - previous) / previous * 100).quantize(Decimal('0.1'))
    return change


def get_month_comparison(user, currency=None):
    if user.organization_id is None:
        return None

    today = timezone.localdate()
    cur_year, cur_month = today.year, today.month

    # Крайній випадок: якщо зараз січень — попередній місяць грудень минулого року
    if cur_month == 1:
        prev_year, prev_month = cur_year - 1, 12
    else:
        prev_year, prev_month = cur_year, cur_month - 1

    currency = currency or default_currency_for(user.organization)
    base_qs = _base_finance_queryset(user).filter(service__currency=currency)
    current = _month_revenue(base_qs, cur_year, cur_month)
    previous = _month_revenue(base_qs, prev_year, prev_month)

    import calendar
    MONTH_NAMES = {
        1: _('January'), 2: _('February'), 3: _('March'), 4: _('April'),
        5: _('May'), 6: _('June'), 7: _('July'), 8: _('August'),
        9: _('September'), 10: _('October'), 11: _('November'), 12: _('December'),
    }

    return {
        'currency': currency,
        'current_label': f"{MONTH_NAMES[cur_month]} {cur_year}",
        'previous_label': f"{MONTH_NAMES[prev_month]} {prev_year}",
        'current': current,
        'previous': previous,
        'revenue_change': _pct_change(current['total_revenue'], previous['total_revenue']),
        'avg_check_change': _pct_change(current['average_check'], previous['average_check']),
        'count_change': _pct_change(Decimal(current['count']), Decimal(previous['count'])),
    }


def _finance_filter_data(query_params):
    data = query_params.copy()
    # За замовчуванням показуємо тільки виконані записи —
    # лише вони мають фактичну вартість і впливають на дохід
    if not data.get('status'):
        data['status'] = AppointmentStatus.COMPLETED
    return data


def _base_finance_queryset(user):
    if user.organization_id is None:
        return Appointment.objects.none()

    return Appointment.objects.select_related(
        'client',
        'service',
        'employee',
    ).filter(organization=user.organization)


def _apply_finance_filters(queryset, cleaned_data, *, include_status=True):
    # include_status=False використовується для підрахунку виконаних записів БЕЗ фактичної вартості:
    # нам потрібен той самий набір фільтрів (дата, послуга, співробітник), але без фільтра статусу,
    # щоб окремо застосувати status=COMPLETED і actual_price__isnull=True
    date_from = cleaned_data.get('date_from')
    date_to = cleaned_data.get('date_to')
    service = cleaned_data.get('service')
    employee = cleaned_data.get('employee')
    status = cleaned_data.get('status')
    currency = cleaned_data.get('currency')

    if currency:
        queryset = queryset.filter(service__currency=currency)
    if date_from:
        queryset = queryset.filter(appointment_date__gte=date_from)
    if date_to:
        queryset = queryset.filter(appointment_date__lte=date_to)
    if service:
        queryset = queryset.filter(service=service)
    if employee:
        queryset = queryset.filter(employee=employee)
    if include_status and status:
        queryset = queryset.filter(status=status)

    return queryset


def get_finance_analytics(user, filter_form):
    if not filter_form.is_valid():
        empty_queryset = Appointment.objects.none()
        return {
            'currency': filter_form.default_currency,
            'paid_appointments': empty_queryset,
            'total_revenue': Decimal('0.00'),
            'average_check': Decimal('0.00'),
            'min_actual_price': Decimal('0.00'),
            'max_actual_price': Decimal('0.00'),
            'revenue_appointments_count': 0,
            'completed_without_price_count': 0,
            'service_revenue': [],
            'employee_revenue': [],
            'date_revenue': [],
        }

    base_queryset = _base_finance_queryset(user)
    filtered_queryset = _apply_finance_filters(
        base_queryset,
        filter_form.cleaned_data,
        include_status=True,
    )
    paid_appointments = filtered_queryset.filter(actual_price__isnull=False)

    totals = paid_appointments.aggregate(
        total_revenue=Sum('actual_price'),
        average_check=Avg('actual_price'),
        min_actual_price=Min('actual_price'),
        max_actual_price=Max('actual_price'),
    )

    completed_without_price_queryset = _apply_finance_filters(
        base_queryset,
        filter_form.cleaned_data,
        include_status=False,
    ).filter(
        status=AppointmentStatus.COMPLETED,
        actual_price__isnull=True,
    )

    service_revenue = list(
        paid_appointments.values('service__name')
        .annotate(
            appointments_count=Count('id'),
            revenue=Sum('actual_price'),
            average_check=Avg('actual_price'),
        )
        .order_by('-revenue', 'service__name')
    )
    employee_revenue = list(
        paid_appointments.values('employee__username')
        .annotate(
            appointments_count=Count('id'),
            revenue=Sum('actual_price'),
            average_check=Avg('actual_price'),
        )
        .order_by('-revenue', 'employee__username')
    )
    date_revenue = list(
        paid_appointments.values('appointment_date')
        .annotate(
            appointments_count=Count('id'),
            revenue=Sum('actual_price'),
        )
        .order_by('-appointment_date')
    )

    return {
        'currency': filter_form.cleaned_data['currency'],
        'paid_appointments': paid_appointments.order_by(
            '-appointment_date',
            '-start_time',
            '-id',
        ),
        'total_revenue': _decimal_or_zero(totals['total_revenue']),
        'average_check': _decimal_or_zero(totals['average_check']),
        'min_actual_price': _decimal_or_zero(totals['min_actual_price']),
        'max_actual_price': _decimal_or_zero(totals['max_actual_price']),
        'revenue_appointments_count': paid_appointments.count(),
        'completed_without_price_count': completed_without_price_queryset.count(),
        'service_revenue': service_revenue,
        'employee_revenue': employee_revenue,
        'date_revenue': date_revenue,
    }


@login_required
def home_view(request):
    analytics = get_dashboard_analytics(request.user)
    appointments = analytics.pop('appointments_queryset')
    onboarding = get_onboarding_status(request.user)
    can_view_financials = request.user.role in {UserRole.ADMIN, UserRole.MANAGER}
    today_revenue = Decimal('0.00')
    today_revenue_by_currency = []

    if not can_view_financials:
        analytics.pop('total_revenue', None)
        analytics.pop('average_check', None)
        analytics.pop('revenue_appointments_count', None)
        analytics.pop('revenue_by_currency', None)
    elif request.user.organization_id is not None:
        today_revenue_by_currency = [
            {'currency': item['service__currency'], 'amount': _decimal_or_zero(item['total'])}
            for item in Appointment.objects.filter(
                organization=request.user.organization,
                appointment_date=timezone.localdate(),
                status=AppointmentStatus.COMPLETED,
                actual_price__isnull=False,
            ).values('service__currency').annotate(total=Sum('actual_price')).order_by('service__currency')
        ]
        if len(today_revenue_by_currency) == 1:
            today_revenue = today_revenue_by_currency[0]['amount']
        elif today_revenue_by_currency:
            today_revenue = None

    nearest_appointments = (
        appointments.exclude(status=AppointmentStatus.CANCELLED)
        .filter(appointment_date__gte=timezone.localdate())
        .order_by('appointment_date', 'start_time')[:5]
    )

    recent_status_changes = AppointmentStatusHistory.objects.select_related(
        'appointment',
        'appointment__client',
        'appointment__service',
        'changed_by',
    ).filter(organization=request.user.organization).order_by('-changed_at')[:5]

    can_manage_data = (
        request.user.organization_id is not None
        and request.user.role in {UserRole.ADMIN, UserRole.MANAGER}
    )
    can_manage_users = (
        request.user.organization_id is not None
        and request.user.role == UserRole.ADMIN
    )
    quick_actions = []

    if can_manage_data:
        quick_actions.extend([
            {
                'label': _('Create appointment'),
                'url': reverse('appointment_create'),
                'style': 'primary',
            },
            {
                'label': _('Add client'),
                'url': reverse('client_create'),
                'style': 'outline-primary',
            },
            {
                'label': _('Add service'),
                'url': reverse('service_create'),
                'style': 'outline-secondary',
            },
        ])

    if can_manage_users:
        quick_actions.append({
            'label': _('Add employee'),
            'url': reverse('user_create'),
            'style': 'outline-secondary',
        })

    context = {
        **analytics,
        'onboarding': onboarding,
        'nearest_appointments': nearest_appointments,
        'recent_status_changes': recent_status_changes,
        'quick_actions': quick_actions,
        'header_quick_actions': quick_actions[:2],
        'can_view_financials': can_view_financials,
        'today_revenue': today_revenue,
        'today_revenue_by_currency': today_revenue_by_currency,
        'default_currency': default_currency_for(request.user.organization),
    }
    return render(request, 'home.html', context)


@manager_or_admin_required
def finance_analytics_view(request):
    filter_data = _finance_filter_data(request.GET)
    filter_form = FinanceAnalyticsFilterForm(
        filter_data,
        organization=request.user.organization,
    )
    analytics = get_finance_analytics(request.user, filter_form)

    query_params = filter_form.data.copy()
    query_params.pop('page', None)
    query_string = query_params.urlencode()

    page_obj = Paginator(
        analytics['paid_appointments'],
        FINANCE_DETAIL_PAGE_SIZE,
    ).get_page(request.GET.get('page'))

    date_revenue_json = json.dumps(
        [
            {
                'appointment_date': str(item['appointment_date']),
                'revenue': float(item['revenue'] or 0),
            }
            for item in analytics.get('date_revenue', [])
        ]
    )

    return render(
        request,
        'config/finance_analytics.html',
        {
            'filter_form': filter_form,
            'query_string': query_string,
            'page_obj': page_obj,
            'month_comparison': get_month_comparison(request.user, analytics['currency']),
            'date_revenue_json': date_revenue_json,
            **analytics,
        },
    )


@manager_or_admin_required
def finance_analytics_export_csv_view(request):
    filter_form = FinanceAnalyticsFilterForm(
        _finance_filter_data(request.GET),
        organization=request.user.organization,
    )
    analytics = get_finance_analytics(request.user, filter_form)

    filename = f'finance_analytics_{timezone.localdate():%Y%m%d}.csv'
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    response.write('\ufeff')

    writer = csv.writer(response, delimiter=';')
    writer.writerow([_('Metric'), _('Value'), _('Currency')])
    writer.writerow([_('Total revenue'), analytics['total_revenue'], analytics['currency']])
    writer.writerow([_('Average transaction value'), analytics['average_check'], analytics['currency']])
    writer.writerow([_('Paid appointments'), analytics['revenue_appointments_count']])
    writer.writerow([
        _('Completed appointments without an actual price'),
        analytics['completed_without_price_count'],
    ])
    writer.writerow([])
    writer.writerow([
        _('Date'),
        _('Client'),
        _('Service'),
        _('Employee'),
        _('Status'),
        _('Service base price'),
        _('Appointment actual price'),
        _('Currency'),
    ])

    for appointment in analytics['paid_appointments']:
        writer.writerow([
            format_csv_date(appointment.appointment_date),
            appointment.client.full_name,
            appointment.service.name,
            appointment.employee.get_full_name() or appointment.employee.username,
            appointment.get_status_display(),
            appointment.service.price,
            appointment.actual_price,
            appointment.service.currency,
        ])

    return response


@admin_required
def admin_dashboard_view(request):
    org = request.user.organization
    org_users = User.objects.filter(organization=org)
    now = timezone.now()
    seven_days_ago = now - timedelta(days=7)
    thirty_days_ago = now - timedelta(days=30)

    # Ролі користувачів
    role_map = dict(User._meta.get_field('role').choices)
    role_stats = [
        {
            'role': role_map.get(item['role'], item['role']),
            'total': item['total'],
        }
        for item in org_users.values('role').annotate(total=Count('id')).order_by('role')
    ]

    # Безпека — входи за 7 днів
    login_qs = AuditLog.objects.filter(
        organization=org,
        action_type=AuditActionType.LOGIN,
        created_at__gte=seven_days_ago,
    )
    login_count_7d = login_qs.count()
    unique_ips_7d = login_qs.exclude(
        ip_address__isnull=True,
    ).values('ip_address').distinct().count()

    recent_auth_logs = AuditLog.objects.filter(
        organization=org,
        action_type__in=[AuditActionType.LOGIN, AuditActionType.LOGOUT],
    ).select_related('user').order_by('-created_at')[:8]

    # Стан організації — попередження
    inactive_users_qs = org_users.filter(
        last_login__lt=thirty_days_ago,
        is_active=True,
    ).exclude(pk=request.user.pk)

    never_logged_in_qs = org_users.filter(
        last_login__isnull=True,
        is_active=True,
    ).exclude(pk=request.user.pk)

    completed_without_price = Appointment.objects.filter(
        organization=org,
        status=AppointmentStatus.COMPLETED,
        actual_price__isnull=True,
    ).count()

    # Адмін-дії — зміни по користувачах
    admin_actions = AuditLog.objects.filter(
        organization=org,
        action_type__in=[
            AuditActionType.ASSIGN_ROLE,
            AuditActionType.CREATE,
            AuditActionType.DELETE,
        ],
        entity_type=AuditEntityType.USER,
    ).select_related('user').order_by('-created_at')[:8]

    context = {
        'users_count': org_users.count(),
        'active_users_count': org_users.filter(is_active=True).count(),
        'role_stats': role_stats,
        # Безпека
        'login_count_7d': login_count_7d,
        'unique_ips_7d': unique_ips_7d,
        'recent_auth_logs': recent_auth_logs,
        # Попередження
        'inactive_users': inactive_users_qs[:5],
        'inactive_users_count': inactive_users_qs.count(),
        'never_logged_in': never_logged_in_qs[:5],
        'never_logged_in_count': never_logged_in_qs.count(),
        'completed_without_price': completed_without_price,
        # Адмін-дії
        'admin_actions': admin_actions,
    }
    return render(request, 'admin_dashboard.html', context)


def health_view(request):
    """Endpoint для моніторингу Railway — повертає HTTP 200 якщо сервер живий."""
    return JsonResponse({"status": "ok"})

