from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path
from django.views.i18n import JavaScriptCatalog
from django_ratelimit.decorators import ratelimit

from django.shortcuts import render

from .views import (
    admin_dashboard_view,
    finance_analytics_export_csv_view,
    finance_analytics_view,
    health_view,
    home_view,
)


def handler404(request, exception):
    return render(request, '404.html', status=404)


def handler500(request):
    return render(request, '500.html', status=500)
from users.forms import OrganizationAuthenticationForm
from users.views import (
    organization_delete_view,
    organization_settings_view,
    profile_password_change_view,
    profile_view,
    signup_view,
)


login_view = ratelimit(
    key='ip',
    rate='5/m',
    method='POST',
    block=True,
)(
    auth_views.LoginView.as_view(
        template_name='registration/login.html',
        authentication_form=OrganizationAuthenticationForm,
    )
)

signup_view = ratelimit(
    key='ip',
    rate='3/m',
    method='POST',
    block=True,
)(signup_view)

urlpatterns = [
    path('i18n/', include('django.conf.urls.i18n')),
    path('jsi18n/', JavaScriptCatalog.as_view(), name='javascript-catalog'),
    path('health/', health_view, name='health'),
    path('orvanta-admin/', admin.site.urls),
    path('', home_view, name='home'),
    path('api/', include('api.urls')),
    path('admin-dashboard/', admin_dashboard_view, name='admin_dashboard'),
    path('analytics/finance/', finance_analytics_view, name='finance_analytics'),
    path(
        'analytics/finance/export/csv/',
        finance_analytics_export_csv_view,
        name='finance_analytics_export_csv',
    ),
    path(
        'login/',
        login_view,
        name='login',
    ),
    path('signup/', signup_view, name='signup'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('profile/', profile_view, name='profile'),
    path('profile/password/', profile_password_change_view, name='profile_password_change'),
    path('settings/organization/', organization_settings_view, name='organization_settings'),
    path('settings/organization/delete/', organization_delete_view, name='organization_delete'),
    path('clients/', include('clients.urls')),
    path('services/', include('services_catalog.urls')),
    path('appointments/', include('appointments.urls')),
    path('audit/', include('audit.urls')),
    path('users/', include('users.urls')),
]
