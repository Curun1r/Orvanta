from datetime import date, time
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from appointments.models import Appointment
from audit.models import AuditActionType, AuditEntityType, AuditLog
from clients.models import Client
from services_catalog.models import Service, ServiceCategory

from .models import Organization, User, UserRole


class SignupFlowTests(TestCase):
    def test_signup_creates_admin_user_organization_and_logs_in(self):
        response = self.client.post(
            reverse('signup'),
            data={
                'username': 'new_owner',
                'email': 'owner@example.com',
                'password1': 'StrongPass123!',
                'password2': 'StrongPass123!',
                'organization_name': 'Ink Owner Studio',
            },
            follow=True,
        )

        self.assertRedirects(response, reverse('home'))

        user = User.objects.get(username='new_owner')
        organization = Organization.objects.get(name='Ink Owner Studio')

        self.assertEqual(user.organization, organization)
        self.assertEqual(user.role, UserRole.ADMIN)
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertEqual(response.wsgi_request.user.pk, user.pk)

    def test_signup_generates_unique_organization_slug(self):
        Organization.objects.create(name='Alpha Org', slug='alpha-org')

        self.client.post(
            reverse('signup'),
            data={
                'username': 'owner_two',
                'email': 'owner2@example.com',
                'password1': 'StrongPass123!',
                'password2': 'StrongPass123!',
                'organization_name': 'Alpha---Org',
            },
        )

        organization = Organization.objects.get(name='Alpha---Org')
        self.assertNotEqual(organization.slug, 'alpha-org')
        self.assertTrue(organization.slug.startswith('alpha-org'))


class OrganizationUserCreateTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name='Org One', slug='org-one')
        self.other_organization = Organization.objects.create(name='Org Two', slug='org-two')

        self.admin_user = User.objects.create_user(
            username='org_admin',
            email='org_admin@example.com',
            password='StrongPass123!',
            role=UserRole.ADMIN,
            organization=self.organization,
        )
        self.manager_user = User.objects.create_user(
            username='org_manager',
            email='org_manager@example.com',
            password='StrongPass123!',
            role=UserRole.MANAGER,
            organization=self.organization,
        )
        self.employee_user = User.objects.create_user(
            username='org_employee',
            email='org_employee@example.com',
            password='StrongPass123!',
            role=UserRole.EMPLOYEE,
            organization=self.organization,
        )

    def test_admin_can_create_manager_and_employee(self):
        self.client.force_login(self.admin_user)

        cases = (
            (UserRole.MANAGER, 'new_manager', 'new_manager@example.com'),
            (UserRole.EMPLOYEE, 'new_employee', 'new_employee@example.com'),
        )
        for role, username, email in cases:
            response = self.client.post(
                reverse('user_create'),
                data={
                    'username': username,
                    'email': email,
                    'password1': 'StrongPass123!',
                    'password2': 'StrongPass123!',
                    'role': role,
                },
            )

            self.assertRedirects(response, reverse('user_list'))
            created_user = User.objects.get(username=username)
            self.assertEqual(created_user.organization, self.organization)
            self.assertEqual(created_user.role, role)
            self.assertTrue(created_user.is_active)
            self.assertFalse(created_user.is_staff)
            self.assertFalse(created_user.is_superuser)

    def test_admin_post_cannot_override_security_fields(self):
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse('user_create'),
            data={
                'username': 'safe_user',
                'email': 'safe_user@example.com',
                'password1': 'StrongPass123!',
                'password2': 'StrongPass123!',
                'role': UserRole.MANAGER,
                'organization': self.other_organization.pk,
                'is_staff': True,
                'is_superuser': True,
            },
        )

        self.assertRedirects(response, reverse('user_list'))
        created_user = User.objects.get(username='safe_user')
        self.assertEqual(created_user.organization, self.organization)
        self.assertFalse(created_user.is_staff)
        self.assertFalse(created_user.is_superuser)

    def test_manager_and_employee_cannot_use_create_endpoint(self):
        for user, username, email in (
            (self.manager_user, 'blocked_from_manager', 'blocked_from_manager@example.com'),
            (self.employee_user, 'blocked_from_employee', 'blocked_from_employee@example.com'),
        ):
            self.client.force_login(user)

            get_response = self.client.get(reverse('user_create'))
            self.assertRedirects(get_response, reverse('home'))

            post_response = self.client.post(
                reverse('user_create'),
                data={
                    'username': username,
                    'email': email,
                    'password1': 'StrongPass123!',
                    'password2': 'StrongPass123!',
                    'role': UserRole.EMPLOYEE,
                },
            )
            self.assertRedirects(post_response, reverse('home'))
            self.assertFalse(User.objects.filter(username=username).exists())

    def test_admin_cannot_create_user_with_disallowed_role(self):
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse('user_create'),
            data={
                'username': 'forbidden_admin',
                'email': 'forbidden_admin@example.com',
                'password1': 'StrongPass123!',
                'password2': 'StrongPass123!',
                'role': UserRole.ADMIN,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username='forbidden_admin').exists())


class UserProfileTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name='Profile Org', slug='profile-org')
        self.other_organization = Organization.objects.create(name='Other Org', slug='other-org')
        self.user = User.objects.create_user(
            username='profile_user',
            email='profile_user@example.com',
            password='StrongPass123!',
            role=UserRole.MANAGER,
            organization=self.organization,
            is_active=True,
            is_staff=False,
            is_superuser=False,
        )

    def test_unauthenticated_user_cannot_open_profile(self):
        response = self.client.get(reverse('profile'))
        self.assertRedirects(response, f"{reverse('login')}?next={reverse('profile')}")

    def test_authenticated_user_can_open_profile(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('profile'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'User profile')
        self.assertContains(response, 'Contact details')
        self.assertContains(response, self.user.username)
        self.assertContains(response, self.organization.name)

    def test_user_can_update_email(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse('profile'),
            data={'email': 'new_profile_email@example.com'},
            follow=True,
        )

        self.assertRedirects(response, reverse('profile'))
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, 'new_profile_email@example.com')
        self.assertContains(response, 'Profile updated successfully.')

    def test_profile_post_cannot_override_protected_fields(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse('profile'),
            data={
                'email': 'secure_profile_email@example.com',
                'role': UserRole.ADMIN,
                'organization': self.other_organization.pk,
                'is_staff': True,
                'is_superuser': True,
                'is_active': False,
            },
            follow=True,
        )

        self.assertRedirects(response, reverse('profile'))
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, 'secure_profile_email@example.com')
        self.assertEqual(self.user.role, UserRole.MANAGER)
        self.assertEqual(self.user.organization, self.organization)
        self.assertFalse(self.user.is_staff)
        self.assertFalse(self.user.is_superuser)
        self.assertTrue(self.user.is_active)

    def test_user_can_change_password_and_stays_authenticated(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse('profile_password_change'),
            data={
                'old_password': 'StrongPass123!',
                'new_password1': 'NewStrongPass456!',
                'new_password2': 'NewStrongPass456!',
            },
            follow=True,
        )

        self.assertRedirects(response, reverse('profile'))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('NewStrongPass456!'))
        self.assertEqual(self.client.session.get('_auth_user_id'), str(self.user.pk))

        profile_response = self.client.get(reverse('profile'))
        self.assertEqual(profile_response.status_code, 200)
        self.assertContains(response, 'Password changed successfully.')

    def test_password_not_changed_with_incorrect_old_password(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse('profile_password_change'),
            data={
                'old_password': 'WrongPass123!',
                'new_password1': 'AnotherStrongPass456!',
                'new_password2': 'AnotherStrongPass456!',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('StrongPass123!'))
        self.assertFalse(self.user.check_password('AnotherStrongPass456!'))


class OrganizationLoginTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name='Login Org', slug='login-org')
        self.other_organization = Organization.objects.create(name='Other Login Org', slug='other-login-org')
        self.user = User.objects.create_user(
            username='login_user',
            email='login_user@example.com',
            password='StrongPass123!',
            role=UserRole.MANAGER,
            organization=self.organization,
        )

    def test_user_can_login_with_correct_organization(self):
        response = self.client.post(
            reverse('login'),
            data={
                'username': 'login_user',
                'password': 'StrongPass123!',
                'organization': 'login-org',
            },
            follow=True,
        )

        self.assertRedirects(response, reverse('home'))
        self.assertEqual(response.wsgi_request.user.pk, self.user.pk)

    def test_user_cannot_login_with_wrong_organization(self):
        response = self.client.post(
            reverse('login'),
            data={
                'username': 'login_user',
                'password': 'StrongPass123!',
                'organization': 'other-login-org',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Invalid sign-in details or organization.')
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_user_cannot_login_without_organization(self):
        response = self.client.post(
            reverse('login'),
            data={
                'username': 'login_user',
                'password': 'StrongPass123!',
                'organization': '',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Invalid sign-in details or organization.')
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_login_failure_uses_generic_message(self):
        wrong_org_response = self.client.post(
            reverse('login'),
            data={
                'username': 'login_user',
                'password': 'StrongPass123!',
                'organization': 'wrong-org',
            },
        )
        wrong_password_response = self.client.post(
            reverse('login'),
            data={
                'username': 'login_user',
                'password': 'WrongPass123!',
                'organization': 'login-org',
            },
        )

        self.assertContains(wrong_org_response, 'Invalid sign-in details or organization.')
        self.assertContains(wrong_password_response, 'Invalid sign-in details or organization.')

    def test_superuser_without_organization_can_still_login(self):
        superuser = User.objects.create_superuser(
            username='global_admin',
            email='global_admin@example.com',
            password='StrongPass123!',
        )

        response = self.client.post(
            reverse('login'),
            data={
                'username': 'global_admin',
                'password': 'StrongPass123!',
                'organization': '',
            },
            follow=True,
        )

        self.assertRedirects(response, reverse('home'))
        self.assertEqual(response.wsgi_request.user.pk, superuser.pk)


class OrganizationSettingsTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name='Org One', slug='org-one')
        self.other_organization = Organization.objects.create(name='Org Two', slug='org-two')

        self.admin_user = User.objects.create_user(
            username='settings_admin',
            email='settings_admin@example.com',
            password='StrongPass123!',
            role=UserRole.ADMIN,
            organization=self.organization,
        )
        self.manager_user = User.objects.create_user(
            username='settings_manager',
            email='settings_manager@example.com',
            password='StrongPass123!',
            role=UserRole.MANAGER,
            organization=self.organization,
        )
        self.employee_user = User.objects.create_user(
            username='settings_employee',
            email='settings_employee@example.com',
            password='StrongPass123!',
            role=UserRole.EMPLOYEE,
            organization=self.organization,
        )
        self.other_admin_user = User.objects.create_user(
            username='other_admin',
            email='other_admin@example.com',
            password='StrongPass123!',
            role=UserRole.ADMIN,
            organization=self.other_organization,
        )

    def test_admin_can_open_organization_settings(self):
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse('organization_settings'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Organization settings')
        self.assertContains(response, self.organization.name)
        self.assertContains(response, self.organization.slug)

    def test_manager_employee_and_anonymous_cannot_open_organization_settings(self):
        for user in (self.manager_user, self.employee_user):
            self.client.force_login(user)

            response = self.client.get(reverse('organization_settings'))

            self.assertRedirects(response, reverse('home'))
            self.client.logout()

        anonymous_response = self.client.get(reverse('organization_settings'))
        self.assertRedirects(
            anonymous_response,
            f"{reverse('login')}?next={reverse('organization_settings')}",
        )

    def test_admin_can_change_organization_name_via_settings(self):
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse('organization_settings'),
            data={
                'name': 'Org One Updated',
            },
            follow=True,
        )

        self.assertRedirects(response, reverse('organization_settings'))
        self.organization.refresh_from_db()
        self.assertEqual(self.organization.name, 'Org One Updated')
        self.assertContains(response, 'Organization settings updated successfully.')

    def test_manager_and_employee_cannot_change_organization_name_via_settings(self):
        for user in (self.manager_user, self.employee_user):
            self.client.force_login(user)

            response = self.client.post(
                reverse('organization_settings'),
                data={
                    'name': 'Blocked Rename',
                    'slug': 'blocked-slug',
                },
                follow=True,
            )
            self.assertRedirects(response, reverse('home'))
            self.assertContains(response, 'You do not have permission to access this page.')

            self.organization.refresh_from_db()
            self.assertEqual(self.organization.name, 'Org One')
            self.assertEqual(self.organization.slug, 'org-one')
            self.client.logout()

    def test_slug_does_not_change_on_name_change_or_slug_tampering(self):
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse('organization_settings'),
            data={
                'name': 'Renamed Organization',
                'slug': 'hacked-slug-value',
            },
            follow=True,
        )

        self.assertRedirects(response, reverse('organization_settings'))
        self.organization.refresh_from_db()
        self.assertEqual(self.organization.name, 'Renamed Organization')
        self.assertEqual(self.organization.slug, 'org-one')

    def test_user_cannot_change_foreign_organization(self):
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse('organization_settings'),
            data={
                'name': 'Org One Secure Rename',
                'organization_id': self.other_organization.pk,
            },
            follow=True,
        )

        self.assertRedirects(response, reverse('organization_settings'))
        self.organization.refresh_from_db()
        self.other_organization.refresh_from_db()
        self.assertEqual(self.organization.name, 'Org One Secure Rename')
        self.assertEqual(self.other_organization.name, 'Org Two')

    def test_profile_no_longer_changes_organization_name_directly(self):
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse('profile'),
            data={
                'organization_submit': '1',
                'name': 'Profile Rename Should Not Apply',
                'slug': 'hacked-slug-value',
            },
            follow=True,
        )

        self.assertRedirects(response, reverse('profile'))
        self.organization.refresh_from_db()
        self.assertEqual(self.organization.name, 'Org One')
        self.assertEqual(self.organization.slug, 'org-one')
        self.assertContains(
            response,
            'Organization settings are available on a separate page.',
        )

    def test_profile_page_shows_organization_settings_link_only_for_admin(self):
        self.client.force_login(self.admin_user)
        admin_response = self.client.get(reverse('profile'))
        self.assertContains(admin_response, reverse('organization_settings'))
        self.assertContains(admin_response, 'Organization settings')
        self.assertNotContains(admin_response, 'name="organization_submit"')

        self.client.force_login(self.manager_user)
        manager_response = self.client.get(reverse('profile'))
        self.assertNotContains(manager_response, reverse('organization_settings'))
        self.assertNotContains(manager_response, 'name="organization_submit"')

    def test_admin_can_delete_organization_with_correct_credentials(self):
        client_record = Client.objects.create(
            full_name='Delete Org Client',
            phone='+380500000001',
            organization=self.organization,
            created_by=self.admin_user,
        )
        category = ServiceCategory.objects.create(
            name='Delete Org Category',
            organization=self.organization,
        )
        service = Service.objects.create(
            name='Delete Org Service',
            price=Decimal('120.00'),
            duration_minutes=60,
            category=category,
            organization=self.organization,
        )
        appointment = Appointment.objects.create(
            client=client_record,
            service=service,
            employee=self.employee_user,
            created_by=self.admin_user,
            appointment_date=date(2026, 5, 6),
            start_time=time(9, 0),
            end_time=time(10, 0),
            organization=self.organization,
        )
        audit_log = AuditLog.objects.create(
            user=self.admin_user,
            organization=self.organization,
            action_type=AuditActionType.UPDATE,
            entity_type=AuditEntityType.USER,
            entity_id=self.admin_user.pk,
            description='Organization deletion fixture.',
        )

        other_admin_pk = self.other_admin_user.pk
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse('organization_delete'),
            data={
                'username': 'settings_admin',
                'organization': 'org-one',
                'password': 'StrongPass123!',
            },
            follow=True,
        )

        self.assertRedirects(response, reverse('login'))
        self.assertFalse(response.wsgi_request.user.is_authenticated)
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertFalse(Organization.objects.filter(pk=self.organization.pk).exists())
        self.assertFalse(User.objects.filter(pk=self.admin_user.pk).exists())
        self.assertFalse(User.objects.filter(pk=self.manager_user.pk).exists())
        self.assertFalse(User.objects.filter(pk=self.employee_user.pk).exists())
        self.assertTrue(User.objects.filter(pk=other_admin_pk).exists())
        self.assertFalse(Client.objects.filter(pk=client_record.pk).exists())
        self.assertFalse(ServiceCategory.objects.filter(pk=category.pk).exists())
        self.assertFalse(Service.objects.filter(pk=service.pk).exists())
        self.assertFalse(Appointment.objects.filter(pk=appointment.pk).exists())
        self.assertFalse(AuditLog.objects.filter(pk=audit_log.pk).exists())

    def test_organization_delete_fails_with_wrong_password(self):
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse('organization_delete'),
            data={
                'username': 'settings_admin',
                'organization': 'org-one',
                'password': 'WrongPass123!',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Password confirmation failed.')
        self.assertTrue(Organization.objects.filter(pk=self.organization.pk).exists())
        self.assertTrue(User.objects.filter(pk=self.admin_user.pk).exists())

    def test_organization_delete_fails_with_wrong_org_name(self):
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse('organization_delete'),
            data={
                'username': 'settings_admin',
                'organization': 'org-two',
                'password': 'StrongPass123!',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'The organization name or slug does not match.')
        self.assertTrue(Organization.objects.filter(pk=self.organization.pk).exists())
        self.assertTrue(Organization.objects.filter(pk=self.other_organization.pk).exists())

    def test_organization_delete_fails_for_non_admin(self):
        self.client.force_login(self.manager_user)

        response = self.client.post(
            reverse('organization_delete'),
            data={
                'username': 'settings_manager',
                'organization': 'org-one',
                'password': 'StrongPass123!',
            },
            follow=True,
        )

        self.assertRedirects(response, reverse('home'))
        self.assertContains(response, 'You do not have permission to access this page.')
        self.assertTrue(Organization.objects.filter(pk=self.organization.pk).exists())


class NavigationUiTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name='Nav Org', slug='nav-org')
        self.admin_user = User.objects.create_user(
            username='nav_admin',
            email='nav_admin@example.com',
            password='StrongPass123!',
            role=UserRole.ADMIN,
            organization=self.organization,
        )
        self.manager_user = User.objects.create_user(
            username='nav_manager',
            email='nav_manager@example.com',
            password='StrongPass123!',
            role=UserRole.MANAGER,
            organization=self.organization,
        )
        self.employee_user = User.objects.create_user(
            username='nav_employee',
            email='nav_employee@example.com',
            password='StrongPass123!',
            role=UserRole.EMPLOYEE,
            organization=self.organization,
        )

    def test_login_page_links_to_signup_without_exposing_developer_admin(self):
        response = self.client.get(reverse('login'))
        self.assertContains(response, f'href="{reverse("signup")}"')
        self.assertNotContains(response, f'href="{reverse("admin:index")}"')

    def test_authenticated_layout_does_not_show_django_admin_link(self):
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, f'href="{reverse("admin:index")}"')

    def test_authenticated_navbar_has_home_link_and_user_dropdown(self):
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            f'<a class="nav-link-custom active" href="{reverse("home")}">Home</a>',
            html=True,
        )
        self.assertContains(response, 'class="user-dropdown"')
        self.assertContains(response, 'class="user-pill"')
        self.assertContains(response, f'href="{reverse("profile")}"')
        self.assertContains(response, reverse('organization_settings'))
        self.assertContains(response, 'Profile')
        self.assertContains(response, 'Organization settings')
        self.assertContains(response, 'Log out')
        self.assertContains(response, self.admin_user.username)
        profile_response = self.client.get(reverse('profile'))
        self.assertContains(profile_response, f'href="{reverse("profile_password_change")}"')

    def test_organization_settings_dropdown_item_is_admin_only(self):
        self.client.force_login(self.admin_user)
        admin_response = self.client.get(reverse('home'))
        self.assertContains(admin_response, 'Organization settings')
        self.assertContains(admin_response, reverse('organization_settings'))

        for user in (self.manager_user, self.employee_user):
            self.client.force_login(user)

            response = self.client.get(reverse('home'))

            self.assertNotContains(response, 'Organization settings')
            self.assertNotContains(response, reverse('organization_settings'))
            self.client.logout()


class UserDeleteTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name='Delete Users Org', slug='delete-users-org')
        self.other_organization = Organization.objects.create(
            name='Other Delete Users Org',
            slug='other-delete-users-org',
        )
        self.admin_user = User.objects.create_user(
            username='delete_admin',
            email='delete_admin@example.com',
            password='StrongPass123!',
            role=UserRole.ADMIN,
            organization=self.organization,
        )
        self.second_admin = User.objects.create_user(
            username='delete_second_admin',
            email='delete_second_admin@example.com',
            password='StrongPass123!',
            role=UserRole.ADMIN,
            organization=self.organization,
        )
        self.employee_user = User.objects.create_user(
            username='delete_employee',
            email='delete_employee@example.com',
            password='StrongPass123!',
            role=UserRole.EMPLOYEE,
            organization=self.organization,
        )
        self.other_user = User.objects.create_user(
            username='delete_other_employee',
            email='delete_other_employee@example.com',
            password='StrongPass123!',
            role=UserRole.EMPLOYEE,
            organization=self.other_organization,
        )

    def test_admin_can_delete_user_in_same_organization(self):
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse('user_delete', args=[self.employee_user.pk]),
            data={'confirm': '1'},
            follow=True,
        )

        self.assertRedirects(response, reverse('user_list'))
        self.assertFalse(User.objects.filter(pk=self.employee_user.pk).exists())
        self.assertContains(response, 'User delete_employee deleted successfully.')

    def test_admin_cannot_delete_user_from_another_organization(self):
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse('user_delete', args=[self.other_user.pk]),
            data={'confirm': '1'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(User.objects.filter(pk=self.other_user.pk).exists())
        self.assertContains(response, 'User not found in your organization.')

    def test_admin_cannot_delete_self(self):
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse('user_delete', args=[self.admin_user.pk]),
            data={'confirm': '1'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(User.objects.filter(pk=self.admin_user.pk).exists())
        self.assertContains(response, 'You cannot delete your own account.')

    def test_admin_cannot_delete_last_admin(self):
        self.second_admin.delete()
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse('user_delete', args=[self.admin_user.pk]),
            data={'confirm': '1'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(User.objects.filter(pk=self.admin_user.pk).exists())
        self.assertContains(response, 'The last administrator of the organization cannot be deleted.')


class UserListPaginationTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name='Users Org', slug='users-org')
        self.other_organization = Organization.objects.create(
            name='Other Users Org',
            slug='other-users-org',
        )
        self.admin_user = User.objects.create_user(
            username='users_admin',
            email='users_admin@example.com',
            password='StrongPass123!',
            role=UserRole.ADMIN,
            organization=self.organization,
        )

        for index in range(12):
            User.objects.create_user(
                username=f'users_employee_{index:02d}',
                email=f'users_employee_{index:02d}@example.com',
                password='StrongPass123!',
                role=UserRole.EMPLOYEE,
                organization=self.organization,
            )
            User.objects.create_user(
                username=f'other_users_employee_{index:02d}',
                email=f'other_users_employee_{index:02d}@example.com',
                password='StrongPass123!',
                role=UserRole.EMPLOYEE,
                organization=self.other_organization,
            )

    def test_user_list_is_paginated_and_organization_scoped(self):
        self.client.force_login(self.admin_user)

        first_page = self.client.get(reverse('user_list'))
        second_page = self.client.get(reverse('user_list'), {'page': '2'})

        self.assertEqual(first_page.status_code, 200)
        self.assertEqual(first_page.context['page_obj'].paginator.count, 13)
        self.assertEqual(len(first_page.context['page_obj']), 10)
        self.assertEqual(len(second_page.context['page_obj']), 3)
        self.assertTrue(
            all(user.organization == self.organization for user in first_page.context['page_obj'])
        )
        self.assertTrue(
            all(user.organization == self.organization for user in second_page.context['page_obj'])
        )

    def test_user_create_button_is_below_page_title_for_admin(self):
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse('user_list'))
        html = response.content.decode()

        title_index = html.index('<h1>Users</h1>')
        create_button_index = html.index('Create user')
        filter_index = html.index('Search and filters')

        self.assertLess(title_index, create_button_index)
        self.assertLess(create_button_index, filter_index)
