from datetime import date, time
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from appointments.models import Appointment, AppointmentStatus
from clients.models import Client
from services_catalog.models import Service, ServiceCategory
from users.models import Organization, User, UserRole

from .views import get_dashboard_analytics, get_onboarding_status


class OnboardingStatusTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(
            name='Onboarding Org',
            slug='onboarding-org',
        )
        self.other_organization = Organization.objects.create(
            name='Other Onboarding Org',
            slug='other-onboarding-org',
        )
        self.admin = User.objects.create_user(
            username='onboarding_admin',
            email='onboarding_admin@example.com',
            password='StrongPass123!',
            role=UserRole.ADMIN,
            organization=self.organization,
        )

    def _step_map(self, user=None):
        status = get_onboarding_status(user or self.admin)
        return {step['key']: step['is_done'] for step in status['steps']}

    def _create_complete_workspace(self, organization, *, username_prefix='workspace'):
        employee = User.objects.create_user(
            username=f'{username_prefix}_employee',
            email=f'{username_prefix}_employee@example.com',
            password='StrongPass123!',
            role=UserRole.EMPLOYEE,
            organization=organization,
            is_active=True,
        )
        client = Client.objects.create(
            full_name=f'{username_prefix.title()} Client',
            phone=f'+3805009{employee.pk:05d}',
            is_active=True,
            organization=organization,
            created_by=self.admin if organization == self.organization else employee,
        )
        category = ServiceCategory.objects.create(
            name=f'{username_prefix.title()} Category',
            organization=organization,
        )
        service = Service.objects.create(
            category=category,
            name=f'{username_prefix.title()} Service',
            price='100.00',
            duration_minutes=60,
            is_active=True,
            organization=organization,
        )
        Appointment.objects.create(
            client=client,
            service=service,
            employee=employee,
            created_by=self.admin if organization == self.organization else employee,
            appointment_date=date(2026, 5, 10),
            start_time=time(10, 0),
            end_time=time(11, 0),
            organization=organization,
        )

    def test_new_admin_with_empty_organization_sees_onboarding_block(self):
        self.client.force_login(self.admin)

        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Set up your organization')
        self.assertContains(response, reverse('category_create'))
        self.assertFalse(response.context['onboarding']['is_complete'])

    def test_manager_and_employee_do_not_see_onboarding_block(self):
        for role in (UserRole.MANAGER, UserRole.EMPLOYEE):
            user = User.objects.create_user(
                username=f'onboarding_{role}',
                email=f'onboarding_{role}@example.com',
                password='StrongPass123!',
                role=role,
                organization=self.organization,
            )
            self.client.force_login(user)

            response = self.client.get(reverse('home'))

            self.assertEqual(response.status_code, 200)
            self.assertIsNone(response.context['onboarding'])
            self.assertNotContains(response, 'Set up your organization')

    def test_complete_workspace_hides_onboarding_block(self):
        self._create_complete_workspace(self.organization)
        self.client.force_login(self.admin)

        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['onboarding']['is_complete'])
        self.assertNotContains(response, 'Set up your organization')

    def test_onboarding_uses_only_current_organization_data(self):
        self._create_complete_workspace(
            self.other_organization,
            username_prefix='foreign_workspace',
        )

        steps = self._step_map()

        self.assertEqual(
            steps,
            {
                'service_category': False,
                'service': False,
                'employee': False,
                'client': False,
                'appointment': False,
            },
        )

    def test_steps_become_done_after_related_objects_exist(self):
        inactive_employee = User.objects.create_user(
            username='inactive_onboarding_employee',
            email='inactive_onboarding_employee@example.com',
            password='StrongPass123!',
            role=UserRole.EMPLOYEE,
            organization=self.organization,
            is_active=False,
        )
        inactive_client = Client.objects.create(
            full_name='Inactive Onboarding Client',
            phone='+380500910000',
            is_active=False,
            organization=self.organization,
            created_by=self.admin,
        )
        category = ServiceCategory.objects.create(
            name='Onboarding Category',
            organization=self.organization,
        )
        inactive_service = Service.objects.create(
            category=category,
            name='Inactive Onboarding Service',
            price='100.00',
            duration_minutes=60,
            is_active=False,
            organization=self.organization,
        )

        steps = self._step_map()

        self.assertTrue(steps['service_category'])
        self.assertFalse(steps['employee'])
        self.assertFalse(steps['client'])
        self.assertFalse(steps['service'])

        inactive_employee.is_active = True
        inactive_employee.save(update_fields=['is_active'])
        inactive_client.is_active = True
        inactive_client.save(update_fields=['is_active'])
        inactive_service.is_active = True
        inactive_service.save(update_fields=['is_active'])
        Appointment.objects.create(
            client=inactive_client,
            service=inactive_service,
            employee=inactive_employee,
            created_by=self.admin,
            appointment_date=date(2026, 5, 11),
            start_time=time(12, 0),
            end_time=time(13, 0),
            organization=self.organization,
        )

        self.assertEqual(
            self._step_map(),
            {
                'service_category': True,
                'service': True,
                'employee': True,
                'client': True,
                'appointment': True,
            },
        )

    def test_home_does_not_crash_for_admin_without_organization(self):
        admin_without_organization = User.objects.create_user(
            username='admin_without_org',
            email='admin_without_org@example.com',
            password='StrongPass123!',
            role=UserRole.ADMIN,
            organization=None,
        )
        self.client.force_login(admin_without_organization)

        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context['onboarding'])
        self.assertNotContains(response, 'Set up your organization')


class DashboardRevenueAnalyticsTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(
            name='Revenue Org',
            slug='revenue-org',
        )
        self.other_organization = Organization.objects.create(
            name='Other Revenue Org',
            slug='other-revenue-org',
        )
        self.admin = User.objects.create_user(
            username='revenue_admin',
            email='revenue_admin@example.com',
            password='StrongPass123!',
            role=UserRole.ADMIN,
            organization=self.organization,
        )
        self.employee = User.objects.create_user(
            username='revenue_employee',
            email='revenue_employee@example.com',
            password='StrongPass123!',
            role=UserRole.EMPLOYEE,
            organization=self.organization,
        )
        self.other_employee = User.objects.create_user(
            username='other_revenue_employee',
            email='other_revenue_employee@example.com',
            password='StrongPass123!',
            role=UserRole.EMPLOYEE,
            organization=self.other_organization,
        )
        self.client_record = Client.objects.create(
            full_name='Revenue Client',
            phone='+380501230001',
            organization=self.organization,
            created_by=self.admin,
        )
        self.other_client_record = Client.objects.create(
            full_name='Other Revenue Client',
            phone='+380501230002',
            organization=self.other_organization,
            created_by=self.other_employee,
        )
        self.category = ServiceCategory.objects.create(
            name='Revenue Category',
            organization=self.organization,
        )
        self.other_category = ServiceCategory.objects.create(
            name='Other Revenue Category',
            organization=self.other_organization,
        )
        self.service = Service.objects.create(
            category=self.category,
            name='Revenue Service',
            price='100.00',
            duration_minutes=60,
            organization=self.organization,
        )
        self.other_service = Service.objects.create(
            category=self.other_category,
            name='Other Revenue Service',
            price='100.00',
            duration_minutes=60,
            organization=self.other_organization,
        )

    def _create_appointment(
        self,
        *,
        organization=None,
        employee=None,
        status=AppointmentStatus.COMPLETED,
        actual_price=None,
        day=1,
    ):
        organization = organization or self.organization
        client = self.client_record
        service = self.service
        created_by = self.admin

        if organization != self.organization:
            client = self.other_client_record
            service = self.other_service
            created_by = self.other_employee
            employee = employee or self.other_employee
        else:
            employee = employee or self.employee

        return Appointment.objects.create(
            client=client,
            service=service,
            employee=employee,
            created_by=created_by,
            appointment_date=date(2026, 6, day),
            start_time=time(10, 0),
            end_time=time(11, 0),
            status=status,
            actual_price=actual_price,
            organization=organization,
        )

    def test_dashboard_revenue_counts_completed_paid_appointments_only(self):
        self._create_appointment(actual_price='100.00', day=1)
        self._create_appointment(actual_price='250.00', day=2)
        self._create_appointment(actual_price=None, day=3)
        self._create_appointment(
            status=AppointmentStatus.CANCELLED,
            actual_price='900.00',
            day=4,
        )
        self._create_appointment(
            status=AppointmentStatus.PLANNED,
            actual_price='800.00',
            day=5,
        )
        self._create_appointment(
            status=AppointmentStatus.CONFIRMED,
            actual_price='700.00',
            day=6,
        )
        self._create_appointment(
            organization=self.other_organization,
            employee=self.other_employee,
            actual_price='1000.00',
            day=7,
        )

        analytics = get_dashboard_analytics(self.admin)

        self.assertEqual(analytics['total_revenue'], Decimal('350.00'))
        self.assertEqual(analytics['average_check'], Decimal('175.00'))
        self.assertEqual(analytics['revenue_appointments_count'], 2)
        self.assertEqual(analytics['planned_count'], 1)
        self.assertEqual(analytics['confirmed_count'], 1)
        self.assertEqual(analytics['completed_without_price_count'], 1)

    def test_dashboard_revenue_defaults_to_zero_without_completed_paid_appointments(self):
        self._create_appointment(status=AppointmentStatus.COMPLETED, actual_price=None)
        self._create_appointment(status=AppointmentStatus.CANCELLED, actual_price='100.00')

        analytics = get_dashboard_analytics(self.admin)

        self.assertEqual(analytics['total_revenue'], Decimal('0.00'))
        self.assertEqual(analytics['average_check'], Decimal('0.00'))
        self.assertEqual(analytics['revenue_appointments_count'], 0)


class DashboardFinancialVisibilityTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(
            name='Financial Visibility Org',
            slug='financial-visibility-org',
        )
        self.admin = User.objects.create_user(
            username='financial_admin',
            email='financial_admin@example.com',
            password='StrongPass123!',
            role=UserRole.ADMIN,
            organization=self.organization,
        )
        self.manager = User.objects.create_user(
            username='financial_manager',
            email='financial_manager@example.com',
            password='StrongPass123!',
            role=UserRole.MANAGER,
            organization=self.organization,
        )
        self.employee = User.objects.create_user(
            username='financial_employee',
            email='financial_employee@example.com',
            password='StrongPass123!',
            role=UserRole.EMPLOYEE,
            organization=self.organization,
        )

    def test_admin_and_manager_see_financial_analytics(self):
        today = timezone.localdate()
        client_record = Client.objects.create(
            full_name='Today Revenue Client',
            phone='+380501111111',
            organization=self.organization,
            created_by=self.admin,
        )
        category = ServiceCategory.objects.create(
            name='Today Revenue Category',
            organization=self.organization,
        )
        service = Service.objects.create(
            category=category,
            name='Today Revenue Service',
            price='100.00',
            duration_minutes=60,
            organization=self.organization,
        )
        Appointment.objects.create(
            client=client_record,
            service=service,
            employee=self.employee,
            created_by=self.admin,
            appointment_date=today,
            start_time=time(10, 0),
            end_time=time(11, 0),
            status=AppointmentStatus.COMPLETED,
            actual_price='125.00',
            organization=self.organization,
        )

        for user in (self.admin, self.manager):
            self.client.force_login(user)

            response = self.client.get(reverse('home'))

            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context['can_view_financials'])
            self.assertEqual(response.context['today_revenue'], Decimal('125.00'))
            self.assertContains(response, 'Revenue today')
            self.assertContains(response, reverse('finance_analytics'))
            self.assertContains(response, 'Finance')
            self.assertNotContains(response, 'Average appointment value')
            self.assertNotContains(response, 'Priced appointments')

    def test_employee_does_not_see_financial_analytics(self):
        self.client.force_login(self.employee)

        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['can_view_financials'])
        self.assertNotContains(response, 'Revenue today')
        self.assertNotContains(response, 'Finance')
        self.assertNotContains(response, 'Average appointment value')
        self.assertNotContains(response, 'Priced appointments')
        self.assertNotIn('total_revenue', response.context)
        self.assertNotIn('average_check', response.context)
        self.assertNotIn('revenue_appointments_count', response.context)


class FinanceAnalyticsTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(
            name='Finance Analytics Org',
            slug='finance-analytics-org',
        )
        self.other_organization = Organization.objects.create(
            name='Other Finance Analytics Org',
            slug='other-finance-analytics-org',
        )
        self.admin = User.objects.create_user(
            username='finance_admin',
            email='finance_admin@example.com',
            password='StrongPass123!',
            role=UserRole.ADMIN,
            organization=self.organization,
        )
        self.manager = User.objects.create_user(
            username='finance_manager',
            email='finance_manager@example.com',
            password='StrongPass123!',
            role=UserRole.MANAGER,
            organization=self.organization,
        )
        self.employee = User.objects.create_user(
            username='finance_employee',
            email='finance_employee@example.com',
            password='StrongPass123!',
            role=UserRole.EMPLOYEE,
            organization=self.organization,
        )
        self.employee_2 = User.objects.create_user(
            username='finance_employee_2',
            email='finance_employee_2@example.com',
            password='StrongPass123!',
            role=UserRole.EMPLOYEE,
            organization=self.organization,
        )
        self.other_employee = User.objects.create_user(
            username='other_finance_employee',
            email='other_finance_employee@example.com',
            password='StrongPass123!',
            role=UserRole.EMPLOYEE,
            organization=self.other_organization,
        )
        self.client_record = Client.objects.create(
            full_name='Finance Client',
            phone='+380502220001',
            organization=self.organization,
            created_by=self.admin,
        )
        self.other_client_record = Client.objects.create(
            full_name='Other Finance Client',
            phone='+380502220002',
            organization=self.other_organization,
            created_by=self.other_employee,
        )
        self.category = ServiceCategory.objects.create(
            name='Finance Category',
            organization=self.organization,
        )
        self.other_category = ServiceCategory.objects.create(
            name='Other Finance Category',
            organization=self.other_organization,
        )
        self.service = Service.objects.create(
            category=self.category,
            name='Finance Service A',
            price='100.00',
            duration_minutes=60,
            organization=self.organization,
        )
        self.service_2 = Service.objects.create(
            category=self.category,
            name='Finance Service B',
            price='200.00',
            duration_minutes=90,
            organization=self.organization,
        )
        self.other_service = Service.objects.create(
            category=self.other_category,
            name='Other Finance Service',
            price='900.00',
            duration_minutes=60,
            organization=self.other_organization,
        )

        self._create_appointment(
            service=self.service,
            employee=self.employee,
            actual_price='100.00',
            day=1,
        )
        self._create_appointment(
            service=self.service_2,
            employee=self.employee_2,
            actual_price='200.00',
            day=2,
        )
        self._create_appointment(
            service=self.service,
            employee=self.employee,
            actual_price=None,
            day=3,
        )
        self._create_appointment(
            service=self.service,
            employee=self.employee,
            status=AppointmentStatus.CANCELLED,
            actual_price='500.00',
            day=4,
        )
        self._create_appointment(
            service=self.service,
            employee=self.employee,
            status=AppointmentStatus.PLANNED,
            actual_price='700.00',
            day=5,
        )
        self._create_appointment(
            organization=self.other_organization,
            client=self.other_client_record,
            service=self.other_service,
            employee=self.other_employee,
            created_by=self.other_employee,
            actual_price='999.00',
            day=2,
        )

    def _create_appointment(
        self,
        *,
        organization=None,
        client=None,
        service=None,
        employee=None,
        created_by=None,
        status=AppointmentStatus.COMPLETED,
        actual_price=None,
        day=1,
    ):
        organization = organization or self.organization
        return Appointment.objects.create(
            client=client or self.client_record,
            service=service or self.service,
            employee=employee or self.employee,
            created_by=created_by or self.admin,
            appointment_date=date(2026, 6, day),
            start_time=time(10, 0),
            end_time=time(11, 0),
            status=status,
            actual_price=actual_price,
            organization=organization,
        )

    def test_admin_and_manager_can_access_finance_analytics(self):
        for user in (self.admin, self.manager):
            self.client.force_login(user)

            response = self.client.get(reverse('finance_analytics'))

            self.assertEqual(response.status_code, 200)
            self.assertContains(response, 'Financial analytics')
            self.assertContains(response, 'Total revenue')
            self.assertContains(response, 'Finance Service A')
            self.assertContains(response, 'Finance Service B')
            self.assertNotContains(response, 'Other Finance Service')

    def test_employee_and_anonymous_cannot_access_finance_analytics(self):
        self.client.force_login(self.employee)
        employee_response = self.client.get(reverse('finance_analytics'))
        self.assertRedirects(employee_response, reverse('home'))

        self.client.logout()
        anonymous_response = self.client.get(reverse('finance_analytics'))
        self.assertRedirects(
            anonymous_response,
            f"{reverse('login')}?next={reverse('finance_analytics')}",
        )

    def test_default_metrics_use_completed_paid_current_organization_only(self):
        self.client.force_login(self.admin)

        response = self.client.get(reverse('finance_analytics'))

        self.assertEqual(response.context['total_revenue'], Decimal('300.00'))
        self.assertEqual(response.context['average_check'], Decimal('150.00'))
        self.assertEqual(response.context['revenue_appointments_count'], 2)
        self.assertEqual(response.context['completed_without_price_count'], 1)

    def test_finance_filters_by_date_service_employee_and_status(self):
        self.client.force_login(self.admin)

        date_response = self.client.get(
            reverse('finance_analytics'),
            {'date_from': '2026-06-02', 'date_to': '2026-06-02'},
        )
        self.assertEqual(date_response.context['total_revenue'], Decimal('200.00'))

        service_response = self.client.get(
            reverse('finance_analytics'),
            {'service': self.service.pk},
        )
        self.assertEqual(service_response.context['total_revenue'], Decimal('100.00'))

        employee_response = self.client.get(
            reverse('finance_analytics'),
            {'employee': self.employee_2.pk},
        )
        self.assertEqual(employee_response.context['total_revenue'], Decimal('200.00'))

        cancelled_response = self.client.get(
            reverse('finance_analytics'),
            {'status': AppointmentStatus.CANCELLED},
        )
        self.assertEqual(cancelled_response.context['total_revenue'], Decimal('500.00'))
        self.assertEqual(cancelled_response.context['revenue_appointments_count'], 1)

    def test_foreign_service_filter_does_not_leak_data(self):
        self.client.force_login(self.admin)

        response = self.client.get(
            reverse('finance_analytics'),
            {'service': self.other_service.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['filter_form'].is_valid())
        self.assertEqual(response.context['total_revenue'], Decimal('0.00'))
        self.assertNotContains(response, 'Other Finance Client')

    def test_finance_csv_respects_access_scope_and_filters(self):
        self.client.force_login(self.manager)

        response = self.client.get(
            reverse('finance_analytics_export_csv'),
            {'service': self.service.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv; charset=utf-8')
        csv_text = response.content.decode('utf-8-sig')
        self.assertIn('Total revenue', csv_text)
        self.assertIn('Date;Client;Service;Employee;Status', csv_text)
        self.assertIn('Finance Service A', csv_text)
        self.assertNotIn('Finance Service B', csv_text)
        self.assertNotIn('Other Finance Client', csv_text)

        self.client.force_login(self.employee)
        employee_response = self.client.get(reverse('finance_analytics_export_csv'))
        self.assertRedirects(employee_response, reverse('home'))
