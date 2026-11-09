from django.contrib import messages
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import ProtectedError
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from django.conf import settings
from audit.context import audit_context
from .decorators import admin_required, organization_required
from .forms import (
    ConfirmDeleteOrganizationForm,
    ConfirmDeleteUserForm,
    OrganizationSettingsForm,
    OrganizationUserCreateForm,
    ProfilePasswordChangeForm,
    SignupForm,
    UserFilterForm,
    UserProfileForm,
    UserRoleForm,
)
from .models import Organization, User, UserRole

USERS_PAGE_SIZE = settings.PAGINATION_PAGE_SIZE


def _organization_users_queryset(user):
    return User.objects.filter(organization=user.organization).order_by('username')


def _get_user_list_context(request, extra_context=None):
    users = _organization_users_queryset(request.user)
    filter_form = UserFilterForm(request.GET or None)

    if filter_form.is_valid():
        query = filter_form.cleaned_data.get('query')
        role = filter_form.cleaned_data.get('role')
        is_active = filter_form.cleaned_data.get('is_active')

        if query:
            users = users.filter(
                Q(username__icontains=query) |
                Q(email__icontains=query)
            )

        if role:
            users = users.filter(role=role)

        if is_active == 'true':
            users = users.filter(is_active=True)
        elif is_active == 'false':
            users = users.filter(is_active=False)

    query_params = request.GET.copy()
    query_params.pop('page', None)
    page_obj = Paginator(users, USERS_PAGE_SIZE).get_page(request.GET.get('page'))

    context = {
        'users': page_obj,
        'filter_form': filter_form,
        'page_obj': page_obj,
        'query_string': query_params.urlencode(),
    }
    if extra_context:
        context.update(extra_context)
    return context


def _render_user_list(request, extra_context=None, status=200):
    return render(
        request,
        'users/user_list.html',
        _get_user_list_context(request, extra_context=extra_context),
        status=status,
    )


def _get_organization_settings_context(
    organization,
    form,
    delete_form=None,
    open_delete_organization_modal=False,
):
    return {
        'form': form,
        'delete_organization_form': delete_form or ConfirmDeleteOrganizationForm(),
        'open_delete_organization_modal': open_delete_organization_modal,
        'organization': organization,
        'users_count': User.objects.filter(organization=organization).count(),
    }


def _generate_unique_organization_slug(name):
    base_slug = slugify(name)[:100] or 'organization'
    slug = base_slug
    suffix = 2

    while Organization.objects.filter(slug=slug).exists():
        suffix_part = f'-{suffix}'
        slug = f'{base_slug[:100 - len(suffix_part)]}{suffix_part}'
        suffix += 1

    return slug


def signup_view(request):
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        form = SignupForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                organization_name = form.cleaned_data['organization_name']
                organization = Organization.objects.create(
                    name=organization_name,
                    slug=_generate_unique_organization_slug(organization_name),
                )

                user = form.save(commit=False)
                user.email = form.cleaned_data['email']
                user.organization = organization
                user.role = UserRole.ADMIN
                user.is_active = True
                user.is_staff = False
                user.is_superuser = False
                with audit_context(user=user):
                    user.save()

            login(request, user)
            messages.success(request, 'Реєстрацію завершено успішно.')
            return redirect('home')
    else:
        form = SignupForm()

    return render(request, 'registration/signup.html', {'form': form})


@admin_required
def user_list_view(request):
    return _render_user_list(request)


@admin_required
@organization_required
def user_create_view(request):

    if request.method == 'POST':
        form = OrganizationUserCreateForm(request.POST)
        if form.is_valid():
            new_user = form.save(commit=False)
            new_user.email = form.cleaned_data['email']
            new_user.role = form.cleaned_data['role']
            new_user.organization = request.user.organization
            new_user.is_active = True
            new_user.is_staff = False
            new_user.is_superuser = False
            new_user.save()

            messages.success(request, 'Користувача успішно створено.')
            return redirect('user_list')
    else:
        form = OrganizationUserCreateForm()

    return render(
        request,
        'users/user_create_form.html',
        {'form': form},
    )


@admin_required
@require_POST
def user_toggle_active_view(request, pk):
    user_obj = get_object_or_404(
        User,
        pk=pk,
        organization=request.user.organization,
    )

    if user_obj == request.user and user_obj.is_active:
        messages.error(request, 'Ви не можете деактивувати власний обліковий запис.')
        return redirect('user_list')

    user_obj.is_active = not user_obj.is_active
    user_obj.save(update_fields=['is_active'])

    if user_obj.is_active:
        messages.success(request, 'Користувача успішно активовано.')
    else:
        messages.success(request, 'Користувача успішно деактивовано.')

    return redirect('user_list')


@admin_required
@require_POST
def user_delete_view(request, pk):
    target_user = User.objects.filter(pk=pk).select_related('organization').first()
    form = ConfirmDeleteUserForm(
        request.POST,
        actor=request.user,
        target_user=target_user,
    )

    if form.is_valid():
        username = target_user.username
        try:
            form.delete()
        except ProtectedError:
            form.add_error(
                None,
                "Користувача не можна видалити, доки з ним пов'язані захищені записи.",
            )
        else:
            messages.success(request, f'Користувача {username} успішно видалено.')
            return redirect('user_list')

    visible_target = target_user
    if target_user is None or target_user.organization_id != request.user.organization_id:
        visible_target = None
        messages.error(request, 'Користувача не знайдено в межах вашої організації.')

    modal_id = f'deleteUserModal{visible_target.pk}' if visible_target is not None else ''
    return _render_user_list(
        request,
        {
            'delete_user_form': form,
            'delete_user_target': visible_target,
            'open_delete_user_modal_id': modal_id,
        },
    )


@admin_required
def user_edit_role_view(request, pk):
    user_obj = get_object_or_404(
        User,
        pk=pk,
        organization=request.user.organization,
    )

    if request.method == 'POST':
        form = UserRoleForm(request.POST, instance=user_obj)
        if form.is_valid():
            new_role = form.cleaned_data['role']
            if user_obj == request.user and new_role != UserRole.ADMIN:
                messages.error(request, 'Ви не можете змінити власну роль адміністратора.')
            else:
                form.save()
                messages.success(request, 'Роль користувача успішно оновлено.')
                return redirect('user_list')
    else:
        form = UserRoleForm(instance=user_obj)

    return render(
        request,
        'users/user_role_form.html',
        {
            'form': form,
            'user_obj': user_obj,
        },
    )


@login_required
def profile_view(request):
    organization = request.user.organization
    if request.method == 'POST':
        if 'organization_submit' in request.POST:
            messages.error(
                request,
                'Налаштування організації доступні на окремій сторінці.',
            )
            return redirect('profile')

        profile_form = UserProfileForm(request.POST, instance=request.user)
        if profile_form.is_valid():
            profile_form.save()
            messages.success(request, 'Профіль успішно оновлено.')
            return redirect('profile')
    else:
        profile_form = UserProfileForm(instance=request.user)

    can_edit_organization = (
        request.user.role == UserRole.ADMIN and organization is not None
    )

    return render(
        request,
        'users/profile.html',
        {
            'profile_form': profile_form,
            'organization': organization,
            'can_edit_organization': can_edit_organization,
        },
    )


@login_required
def profile_password_change_view(request):
    if request.method == 'POST':
        form = ProfilePasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, 'Пароль успішно змінено.')
            return redirect('profile')
    else:
        form = ProfilePasswordChangeForm(request.user)

    return render(
        request,
        'users/password_change.html',
        {
            'form': form,
        },
    )


@admin_required
@organization_required
def organization_settings_view(request):
    organization = request.user.organization

    if request.method == 'POST':
        form = OrganizationSettingsForm(request.POST, instance=organization)
        if form.is_valid():
            form.save()
            messages.success(request, 'Налаштування організації успішно оновлено.')
            return redirect('organization_settings')
    else:
        form = OrganizationSettingsForm(instance=organization)

    return render(
        request,
        'users/organization_settings.html',
        _get_organization_settings_context(organization, form),
    )


@admin_required
@organization_required
@require_POST
def organization_delete_view(request):
    organization = request.user.organization
    settings_form = OrganizationSettingsForm(instance=organization)
    delete_form = ConfirmDeleteOrganizationForm(request.POST, user=request.user)

    if delete_form.is_valid():
        organization_name = organization.name
        logout(request)
        delete_form.delete()
        messages.success(request, f'Організацію "{organization_name}" успішно видалено.')
        return redirect('login')

    return render(
        request,
        'users/organization_settings.html',
        _get_organization_settings_context(
            organization,
            settings_form,
            delete_form=delete_form,
            open_delete_organization_modal=True,
        ),
    )


@require_POST
@login_required
def toggle_compact_ui_view(request):
    user = request.user
    user.hide_section_subtitles = not user.hide_section_subtitles
    user.save(update_fields=['hide_section_subtitles'])
    return redirect(request.POST.get('next', 'profile'))
