from django.utils.translation import gettext as _, pgettext
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
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
from users.decorators import manager_or_admin_required, organization_required

from .forms import ServiceCategoryForm, ServiceFilterForm, ServiceForm
from .models import Service, ServiceCategory

SERVICES_PAGE_SIZE = settings.PAGINATION_PAGE_SIZE


def _organization_services_queryset(user):
    if user.organization_id is None:
        return Service.objects.none()
    return Service.objects.select_related('category').filter(
        organization=user.organization,
    )


def _filtered_services_queryset(user, data):
    services = _organization_services_queryset(user)

    filter_form = ServiceFilterForm(
        data or None,
        organization=user.organization,
    )

    if filter_form.is_valid():
        query = filter_form.cleaned_data.get('query')
        category = filter_form.cleaned_data.get('category')
        is_active = filter_form.cleaned_data.get('is_active')

        if query:
            services = services.filter(
                Q(name__icontains=query) |
                Q(description__icontains=query)
            )

        if category:
            services = services.filter(category=category)

        if is_active == 'true':
            services = services.filter(is_active=True)
        elif is_active == 'false':
            services = services.filter(is_active=False)

    return services, filter_form


@login_required
def category_list_view(request):
    categories = ServiceCategory.objects.filter(organization=request.user.organization)
    return render(request, 'services_catalog/category_list.html', {'categories': categories})


@manager_or_admin_required
@organization_required
def category_create_view(request):
    if request.method == 'POST':
        form = ServiceCategoryForm(request.POST)
        if form.is_valid():
            category = form.save(commit=False)
            category.organization = request.user.organization
            category.save()
            messages.success(request, _('Service category created successfully.'))
            return redirect('category_list')
    else:
        form = ServiceCategoryForm()

    return render(request, 'services_catalog/category_form.html', {
        'form': form,
        'title': _('Add service category'),
    })


@manager_or_admin_required
def category_update_view(request, pk):
    category = get_object_or_404(
        ServiceCategory,
        pk=pk,
        organization=request.user.organization,
    )

    if request.method == 'POST':
        form = ServiceCategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            messages.success(request, _('Service category updated successfully.'))
            return redirect('category_list')
    else:
        form = ServiceCategoryForm(instance=category)

    return render(request, 'services_catalog/category_form.html', {
        'form': form,
        'title': _('Edit service category'),
    })


@login_required
def service_list_view(request):
    services, filter_form = _filtered_services_queryset(request.user, request.GET)
    return filtered_paginated_response(
        request, services, SERVICES_PAGE_SIZE,
        'services_catalog/service_list.html',
        extra_context={'filter_form': filter_form},
    )


@login_required
def service_export_csv_view(request):
    services, _filter_form = _filtered_services_queryset(request.user, request.GET)
    filename = f'services_export_{timezone.localdate():%Y%m%d}.csv'
    headers = [
        'ID',
        _('Name'),
        _('Category'),
        _('Description'),
        _('Base price'),
        _('Duration, min'),
        pgettext('service status', 'Active'),
        _('Created at'),
        _('Updated at'),
        _('Currency'),
    ]
    rows = (
        [
            service.pk,
            service.name,
            service.category.name if service.category else '',
            service.description,
            service.price,
            service.duration_minutes,
            format_csv_bool(service.is_active),
            format_csv_datetime(service.created_at),
            format_csv_datetime(service.updated_at),
            service.currency,
        ]
        for service in services
    )

    return build_csv_response(filename, headers, rows)


@manager_or_admin_required
@organization_required
def service_create_view(request):
    if request.method == 'POST':
        form = ServiceForm(request.POST, organization=request.user.organization)
        if form.is_valid():
            service = form.save(commit=False)
            service.organization = request.user.organization
            service.save()
            messages.success(request, _('Service created successfully.'))
            return redirect('service_list')
    else:
        form = ServiceForm(organization=request.user.organization)

    return render(request, 'services_catalog/service_form.html', {
        'form': form,
        'title': _('Add service'),
    })


@manager_or_admin_required
def service_update_view(request, pk):
    service = get_object_or_404(
        Service,
        pk=pk,
        organization=request.user.organization,
    )

    if request.method == 'POST':
        form = ServiceForm(
            request.POST,
            instance=service,
            organization=request.user.organization,
        )
        if form.is_valid():
            updated_service = form.save(commit=False)
            updated_service.organization = request.user.organization
            updated_service.save()
            messages.success(request, _('Service updated successfully.'))
            return redirect('service_list')
    else:
        form = ServiceForm(
            instance=service,
            organization=request.user.organization,
        )

    return render(request, 'services_catalog/service_form.html', {
        'form': form,
        'title': _('Edit service'),
    })


@login_required
def service_detail_view(request, pk):
    service = get_object_or_404(
        Service.objects.select_related('category').filter(
            organization=request.user.organization,
        ),
        pk=pk,
    )
    return render(request, 'services_catalog/service_detail.html', {'service': service})


@manager_or_admin_required
@require_POST
def service_toggle_active_view(request, pk):
    service = get_object_or_404(
        Service,
        pk=pk,
        organization=request.user.organization,
    )
    service.is_active = not service.is_active
    service.save(update_fields=['is_active', 'updated_at'])

    if service.is_active:
        messages.success(request, _('Service activated successfully.'))
    else:
        messages.success(request, _('Service deactivated successfully.'))

    return redirect('service_list')
