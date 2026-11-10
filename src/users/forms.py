from django.utils.translation import gettext_lazy as _, pgettext_lazy
from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm, UserCreationForm
from django.db import transaction
from django.db.models import Q

from config.form_ui import BootstrapFormMixin

from .models import Organization, User, UserRole

SAFE_CREATE_ROLE_CHOICES = [
    (UserRole.MANAGER, dict(UserRole.choices)[UserRole.MANAGER]),
    (UserRole.EMPLOYEE, dict(UserRole.choices)[UserRole.EMPLOYEE]),
]


class UserFilterForm(forms.Form):
    query = forms.CharField(
        required=False,
        label=_('Search'),
        widget=forms.TextInput(attrs={'placeholder': _('Username or email')}),
    )
    role = forms.ChoiceField(
        required=False,
        label=_('Role'),
        choices=[('', _('All roles'))] + list(UserRole.choices),
    )
    is_active = forms.ChoiceField(
        required=False,
        label=_('Status'),
        choices=[
            ('', _('All')),
            ('true', pgettext_lazy('summary', 'Active')),
            ('false', pgettext_lazy('summary', 'Inactive')),
        ],
    )


def _configure_user_creation_fields(fields):
    fields['username'].label = _('Username')
    fields['username'].help_text = _('Up to 150 characters. Letters, digits and @/./+/-/_ are allowed.')
    fields['username'].widget.attrs.setdefault('placeholder', 'username')

    fields['email'].widget.attrs.setdefault('placeholder', 'user@example.com')

    fields['password1'].label = _('Password')
    fields['password1'].help_text = _('Use a strong password that meets the system requirements.')
    fields['password1'].widget.attrs.setdefault('placeholder', _('Password'))

    fields['password2'].label = _('Confirm password')
    fields['password2'].help_text = _('Enter the same password again.')
    fields['password2'].widget.attrs.setdefault('placeholder', '••••••••')


class UserRoleForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = User
        fields = ['role']
        labels = {
            'role': _('Role'),
        }


class SignupForm(BootstrapFormMixin, UserCreationForm):
    email = forms.EmailField(label='Email', required=True)
    organization_name = forms.CharField(label=_('Organization name'), max_length=255)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'email', 'password1', 'password2', 'organization_name')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _configure_user_creation_fields(self.fields)
        self.fields['password1'].widget.attrs['placeholder'] = 'A–Z, a–z, 0–9, ! @ # $ % ^ & * ( ) _ - + ='
        self.fields['organization_name'].widget.attrs.setdefault(
            'placeholder',
            _('Enter your organization name'),
        )

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(_('A user with this email address already exists.'))
        return email

    def clean_organization_name(self):
        organization_name = self.cleaned_data['organization_name'].strip()
        if not organization_name:
            raise forms.ValidationError(_('Enter the organization name.'))
        if Organization.objects.filter(name__iexact=organization_name).exists():
            raise forms.ValidationError(_('An organization with this name already exists.'))
        return organization_name


class OrganizationUserCreateForm(BootstrapFormMixin, UserCreationForm):
    email = forms.EmailField(label='Email', required=True)
    role = forms.ChoiceField(label=_('Role'), choices=SAFE_CREATE_ROLE_CHOICES)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'email', 'password1', 'password2', 'role')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _configure_user_creation_fields(self.fields)

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(_('A user with this email address already exists.'))
        return email

    def clean_role(self):
        role = self.cleaned_data['role']
        if role not in {UserRole.MANAGER, UserRole.EMPLOYEE}:
            raise forms.ValidationError(_('Invalid role for creating a user.'))
        return role


class UserProfileForm(BootstrapFormMixin, forms.ModelForm):
    email = forms.EmailField(label='Email', required=True)

    class Meta:
        model = User
        fields = ['email']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['email'].widget.attrs.setdefault('placeholder', 'user@example.com')

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError(_('A user with this email address already exists.'))
        return email


class OrganizationSettingsForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Organization
        fields = ['name']
        labels = {
            'name': _('Organization name'),
        }
        help_texts = {
            'name': _('The organization slug is used to sign in and does not change automatically.'),
        }
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': _('Organization name')}),
        }


class ConfirmDeleteUserForm(forms.Form):
    confirm = forms.BooleanField(widget=forms.HiddenInput, required=True)

    def __init__(self, *args, actor=None, target_user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.actor = actor
        self.target_user = target_user

    def clean(self):
        cleaned_data = super().clean()

        if self.actor is None or self.actor.role != UserRole.ADMIN:
            raise forms.ValidationError(_('You do not have permission to delete users.'))

        if self.actor.organization_id is None:
            raise forms.ValidationError(_('Users cannot be deleted without an organization.'))

        if self.target_user is None:
            raise forms.ValidationError(_('User not found in your organization.'))

        if self.target_user.organization_id != self.actor.organization_id:
            raise forms.ValidationError(_('User not found in your organization.'))

        if self.target_user.role == UserRole.ADMIN:
            admins_count = User.objects.filter(
                organization=self.actor.organization,
                role=UserRole.ADMIN,
            ).count()
            if admins_count <= 1:
                raise forms.ValidationError(
                    _('The last administrator of the organization cannot be deleted.'),
                )

        if self.target_user.pk == self.actor.pk:
            raise forms.ValidationError(_('You cannot delete your own account.'))

        if self.target_user.employee_appointments.exists():
            raise forms.ValidationError(
                _('This user cannot be deleted while appointments are assigned to them. Reassign or delete those appointments first.'),
            )

        return cleaned_data

    def delete(self):
        self.target_user.delete()


class ConfirmDeleteOrganizationForm(BootstrapFormMixin, forms.Form):
    username = forms.CharField(label=_('Username'), max_length=150)
    organization = forms.CharField(label=_('Organization name or slug'), max_length=255)
    password = forms.CharField(label=_('Password'), widget=forms.PasswordInput)

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.organization_obj = getattr(user, 'organization', None)
        self.fields['username'].widget.attrs.setdefault('placeholder', 'username')
        self.fields['organization'].widget.attrs.setdefault('placeholder', _('name or slug'))
        self.fields['password'].widget.attrs.setdefault('placeholder', 'password')

    def clean_username(self):
        username = self.cleaned_data['username'].strip()
        if self.user is None or username != self.user.username:
            raise forms.ValidationError(_('The username does not match the current account.'))
        return username

    def clean_organization(self):
        organization_value = self.cleaned_data['organization'].strip()
        organization = self.organization_obj
        if organization is None:
            raise forms.ValidationError(_('Your account is not linked to an organization.'))

        if organization_value not in {organization.name, organization.slug}:
            raise forms.ValidationError(_('The organization name or slug does not match.'))

        return organization_value

    def clean_password(self):
        password = self.cleaned_data['password']
        if self.user is None:
            raise forms.ValidationError(_('Password confirmation failed.'))

        authenticated_user = authenticate(username=self.user.username, password=password)
        if authenticated_user is None or authenticated_user.pk != self.user.pk:
            raise forms.ValidationError(_('Password confirmation failed.'))

        return password

    def clean(self):
        cleaned_data = super().clean()

        if self.user is None or self.user.role != UserRole.ADMIN:
            raise forms.ValidationError(_('You do not have permission to delete the organization.'))

        if self.organization_obj is None:
            raise forms.ValidationError(_('Your account is not linked to an organization.'))

        return cleaned_data

    def delete(self):
        from appointments.models import Appointment, AppointmentStatusHistory
        from audit.models import AuditLog
        from clients.models import Client
        from services_catalog.models import Service, ServiceCategory

        organization = Organization.objects.get(pk=self.organization_obj.pk)
        user_ids = list(
            User.objects.filter(organization=organization).values_list('pk', flat=True),
        )
        appointment_ids = list(
            Appointment.objects.filter(
                Q(organization=organization) |
                Q(client__organization=organization) |
                Q(service__organization=organization) |
                Q(employee__organization=organization),
            ).values_list('pk', flat=True)
        )

        with transaction.atomic():
            AppointmentStatusHistory.objects.filter(
                Q(organization=organization) |
                Q(appointment_id__in=appointment_ids),
            ).delete()
            Appointment.objects.filter(pk__in=appointment_ids).delete()
            Client.objects.filter(organization=organization).delete()
            Service.objects.filter(organization=organization).delete()
            ServiceCategory.objects.filter(organization=organization).delete()
            AuditLog.objects.filter(
                Q(organization=organization) |
                Q(user_id__in=user_ids),
            ).delete()
            User.objects.filter(organization=organization).delete()
            AuditLog.objects.filter(organization=organization).delete()
            organization.delete()


class ProfilePasswordChangeForm(BootstrapFormMixin, PasswordChangeForm):
    def __init__(self, user, *args, **kwargs):
        super().__init__(user, *args, **kwargs)
        self.fields['old_password'].label = _('Current password')
        self.fields['old_password'].widget.attrs.setdefault('placeholder', _('Current password'))

        self.fields['new_password1'].label = _('New password')
        self.fields['new_password1'].help_text = (
            _('Use a strong password that meets the system requirements.')
        )
        self.fields['new_password1'].widget.attrs.setdefault('placeholder', _('New password'))

        self.fields['new_password2'].label = _('Confirm new password')
        self.fields['new_password2'].help_text = _('Enter the new password again.')
        self.fields['new_password2'].widget.attrs.setdefault(
            'placeholder',
            '••••••••',
        )


class OrganizationAuthenticationForm(AuthenticationForm):
    organization = forms.CharField(
        label=_('Organization'),
        required=False,
        max_length=255,
    )

    error_messages = {
        'invalid_login': _('Invalid sign-in details or organization.'),
        'inactive': _('This account is inactive.'),
    }

    def __init__(self, request=None, *args, **kwargs):
        super().__init__(request, *args, **kwargs)
        self.order_fields(['username', 'password', 'organization'])
        self.fields['username'].label = _('Username')
        self.fields['username'].widget.attrs.setdefault('placeholder', 'username')
        self.fields['password'].label = _('Password')
        self.fields['password'].widget.attrs.setdefault('placeholder', 'password')
        self.fields['organization'].widget.attrs.setdefault('placeholder', _('slug or name'))

        for field in self.fields.values():
            existing_class = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = f'{existing_class} form-control'.strip()

    def clean(self):
        cleaned_data = super().clean()
        user = self.get_user()
        organization_value = (cleaned_data.get('organization') or '').strip()

        if user is None:
            return cleaned_data

        if user.is_superuser and user.organization_id is None and not organization_value:
            return cleaned_data

        if not organization_value:
            raise self.get_invalid_login_error()

        organization = Organization.objects.filter(
            Q(slug__iexact=organization_value) | Q(name__iexact=organization_value),
        ).first()

        if organization is None:
            raise self.get_invalid_login_error()

        if user.organization_id != organization.id:
            raise self.get_invalid_login_error()

        if user.organization_id is None:
            raise self.get_invalid_login_error()

        return cleaned_data
