from django.utils.translation import gettext as _
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect

from .models import UserRole


def role_required(allowed_roles):
    """Фабрика декораторів: повертає декоратор що обмежує доступ до view за роллю користувача."""
    def decorator(view_func):
        @login_required
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if request.user.role not in allowed_roles:
                messages.error(request, _('You do not have permission to access this page.'))
                return redirect('home')
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


# Готові декоратори для трьох рівнів доступу в системі
admin_required = role_required([UserRole.ADMIN])
manager_or_admin_required = role_required([UserRole.ADMIN, UserRole.MANAGER])
employee_manager_admin_required = role_required(
    [UserRole.ADMIN, UserRole.MANAGER, UserRole.EMPLOYEE]
)


def organization_required(view_func):
    """Блокує доступ якщо користувач не прив'язаний до жодної організації.
    Використовується для view що створюють об'єкти — щоб гарантувати наявність organization_id."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not hasattr(request.user, 'organization') or request.user.organization is None:
            messages.error(request, _('Your account is not linked to an organization.'))
            return redirect('home')
        return view_func(request, *args, **kwargs)
    return wrapper
