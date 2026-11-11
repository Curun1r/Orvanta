import csv
import io
from datetime import time, timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from appointments.models import Appointment, AppointmentStatus
from clients.models import Client
from services_catalog.currencies import Currency
from services_catalog.models import Service
from users.models import Organization, User, UserRole

from .views import get_dashboard_analytics, get_month_comparison


class CurrencyReportingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.organization = Organization.objects.create(name='Mixed Currency Studio', slug='mixed-currency')
        cls.admin = User.objects.create_user(username='currency_admin', organization=cls.organization, role=UserRole.ADMIN)
        cls.employee = User.objects.create_user(username='currency_employee', organization=cls.organization, role=UserRole.EMPLOYEE)
        cls.colleague = User.objects.create_user(username='currency_colleague', organization=cls.organization, role=UserRole.EMPLOYEE)
        cls.client_record = Client.objects.create(full_name='English Demo Client', phone='+3530000001', organization=cls.organization)
        cls.services = {}
        for code, amount in ((Currency.EUR, '100.00'), (Currency.USD, '300.00'), (Currency.UAH, '500.00')):
            service = Service.objects.create(name=f'{code} service', price=amount, currency=code, duration_minutes=60, organization=cls.organization)
            cls.services[code] = service
            Appointment.objects.create(
                client=cls.client_record, service=service, organization=cls.organization,
                employee=cls.colleague if code == Currency.USD else cls.employee,
                appointment_date=timezone.localdate(), start_time=time(10), end_time=time(11),
                status=AppointmentStatus.COMPLETED, actual_price=amount,
            )
        cls.other_organization = Organization.objects.create(name='Separate Currency Studio', slug='separate-currency')
        cls.other_admin = User.objects.create_user(username='currency_other_admin', organization=cls.other_organization, role=UserRole.ADMIN)
        cls.other_employee = User.objects.create_user(username='currency_other_employee', organization=cls.other_organization, role=UserRole.EMPLOYEE)
        cls.other_client = Client.objects.create(full_name='Foreign Currency Client', phone='+3530000002', organization=cls.other_organization)
        cls.other_service = Service.objects.create(name='Foreign EUR Service', price='999.00', currency=Currency.EUR, duration_minutes=60, organization=cls.other_organization)
        Appointment.objects.create(
            client=cls.other_client, service=cls.other_service, organization=cls.other_organization,
            employee=cls.other_employee, appointment_date=timezone.localdate(),
            start_time=time(10), end_time=time(11), status=AppointmentStatus.COMPLETED, actual_price='999.00',
        )

    def setUp(self):
        self.client.force_login(self.admin)

    def test_dashboard_home_and_client_keep_each_currency_separate(self):
        analytics = get_dashboard_analytics(self.admin)
        self.assertIsNone(analytics['total_revenue'])
        self.assertIsNone(analytics['average_check'])
        self.assertIsNone(analytics['currency'])
        expected = {'EUR': Decimal('100.00'), 'USD': Decimal('300.00'), 'UAH': Decimal('500.00')}
        self.assertEqual({row['currency']: row['total_revenue'] for row in analytics['revenue_by_currency']}, expected)
        home = self.client.get(reverse('home'))
        self.assertIsNone(home.context['today_revenue'])
        self.assertEqual({row['currency']: row['amount'] for row in home.context['today_revenue_by_currency']}, expected)
        detail = self.client.get(reverse('client_detail', args=[self.client_record.pk]))
        self.assertIsNone(detail.context['total_spent'])
        self.assertEqual({row['currency']: row['amount'] for row in detail.context['total_spent_by_currency']}, expected)

    def test_finance_filter_and_csv_include_only_selected_currency(self):
        response = self.client.get(reverse('finance_analytics'), {'currency': 'EUR'})
        self.assertEqual(response.context['currency'], 'EUR')
        self.assertEqual(response.context['total_revenue'], Decimal('100.00'))
        self.assertEqual(response.context['revenue_appointments_count'], 1)
        self.assertContains(response, 'data-currency="EUR"')
        self.assertIn('currency=EUR', response.context['query_string'])
        export = self.client.get(reverse('finance_analytics_export_csv'), {'currency': 'EUR'})
        rows = list(csv.reader(io.StringIO(export.content.decode('utf-8-sig')), delimiter=';'))
        self.assertEqual(rows[1][1:], ['100.00', 'EUR'])
        header_index = next(index for index, row in enumerate(rows) if row and row[0] == 'Date')
        self.assertEqual(rows[header_index][-1], 'Currency')
        self.assertEqual(len(rows[header_index + 1:]), 1)
        self.assertEqual(rows[-1][-1], 'EUR')
        self.assertNotIn('Foreign EUR Service', export.content.decode('utf-8-sig'))
        mismatch = self.client.get(reverse('finance_analytics'), {'currency': 'EUR', 'service': self.services[Currency.USD].pk})
        self.assertEqual(mismatch.context['total_revenue'], Decimal('0.00'))

    def test_month_comparison_uses_the_same_currency(self):
        previous_month = timezone.localdate().replace(day=1) - timedelta(days=1)
        for code, amount in ((Currency.EUR, '50.00'), (Currency.USD, '900.00')):
            Appointment.objects.create(
                client=self.client_record, service=self.services[code], organization=self.organization,
                employee=self.employee, appointment_date=previous_month, start_time=time(10), end_time=time(11),
                status=AppointmentStatus.COMPLETED, actual_price=amount,
            )
        comparison = get_month_comparison(self.admin, 'EUR')
        self.assertEqual(comparison['current']['total_revenue'], Decimal('100.00'))
        self.assertEqual(comparison['previous']['total_revenue'], Decimal('50.00'))
        response = self.client.get(reverse('finance_analytics'), {'currency': 'EUR'})
        self.assertEqual(response.context['month_comparison']['currency'], 'EUR')
        self.assertEqual(response.context['month_comparison']['previous']['total_revenue'], Decimal('50.00'))

    def test_employee_api_groups_only_assigned_records_and_cannot_open_finance(self):
        self.client.force_login(self.employee)
        response = self.client.get(reverse('api-dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()['total_revenue'])
        self.assertEqual({row['currency'] for row in response.json()['revenue_by_currency']}, {'EUR', 'UAH'})
        self.assertRedirects(self.client.get(reverse('finance_analytics')), reverse('home'))
        self.assertRedirects(self.client.get(reverse('finance_analytics_export_csv')), reverse('home'))

    def test_eur_only_organization_defaults_to_eur_and_rejects_foreign_service(self):
        self.client.force_login(self.other_admin)
        response = self.client.get(reverse('finance_analytics'))
        self.assertEqual(response.context['currency'], 'EUR')
        self.assertEqual(response.context['total_revenue'], Decimal('999.00'))
        response = self.client.get(reverse('finance_analytics'), {'currency': 'EUR', 'service': self.services[Currency.EUR].pk})
        self.assertFalse(response.context['filter_form'].is_valid())
        self.assertEqual(response.context['total_revenue'], Decimal('0.00'))
