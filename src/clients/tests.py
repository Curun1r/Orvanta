from datetime import date, time
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from appointments.models import Appointment, AppointmentStatus
from services_catalog.models import Service, ServiceCategory
from users.models import Organization, User, UserRole

from .models import Client


class ClientListPaginationTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name='Client Org', slug='client-org')
        self.user = User.objects.create_user(
            username='client_manager',
            email='client_manager@example.com',
            password='StrongPass123!',
            role=UserRole.MANAGER,
            organization=self.organization,
        )

    def _create_clients(self, count, *, name_prefix='Client', is_active=True, start_index=0):
        for index in range(count):
            phone_index = start_index + index
            Client.objects.create(
                full_name=f'{name_prefix} {index:02d}',
                phone=f'+38050100{phone_index:04d}',
                email=f'{name_prefix.lower()}_{index:02d}@example.com',
                is_active=is_active,
                organization=self.organization,
                created_by=self.user,
            )

    def test_client_list_is_limited_to_page_size(self):
        self._create_clients(12)
        self.client.force_login(self.user)

        response = self.client.get(reverse('client_list'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['page_obj']), 10)
        self.assertEqual(response.context['page_obj'].paginator.count, 12)

    def test_client_pagination_keeps_filter_query_params(self):
        self._create_clients(12, name_prefix='Filtered')
        self._create_clients(2, name_prefix='Inactive', is_active=False, start_index=100)
        self.client.force_login(self.user)

        response = self.client.get(
            reverse('client_list'),
            {'query': 'Filtered', 'is_active': 'true', 'page': '2'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            'href="?query=Filtered&amp;is_active=true&amp;page=1"',
        )
        self.assertEqual(response.context['query_string'], 'query=Filtered&is_active=true')

    def test_invalid_page_does_not_crash(self):
        self._create_clients(12)
        self.client.force_login(self.user)

        response = self.client.get(reverse('client_list'), {'page': 'invalid'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['page_obj'].number, 1)

    def test_second_page_returns_different_clients(self):
        self._create_clients(12)
        self.client.force_login(self.user)

        first_page = self.client.get(reverse('client_list'), {'page': '1'})
        second_page = self.client.get(reverse('client_list'), {'page': '2'})

        first_page_ids = {client.pk for client in first_page.context['page_obj']}
        second_page_ids = {client.pk for client in second_page.context['page_obj']}

        self.assertEqual(len(first_page_ids), 10)
        self.assertEqual(len(second_page_ids), 2)
        self.assertTrue(first_page_ids.isdisjoint(second_page_ids))


class ClientExportCsvTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name='CSV Client Org', slug='csv-client-org')
        self.other_organization = Organization.objects.create(
            name='Other CSV Client Org',
            slug='other-csv-client-org',
        )
        self.user = User.objects.create_user(
            username='csv_client_manager',
            email='csv_client_manager@example.com',
            password='StrongPass123!',
            role=UserRole.MANAGER,
            organization=self.organization,
        )
        self.other_user = User.objects.create_user(
            username='csv_client_other_manager',
            email='csv_client_other_manager@example.com',
            password='StrongPass123!',
            role=UserRole.MANAGER,
            organization=self.other_organization,
        )

    def _csv_text(self, response):
        return response.content.decode('utf-8-sig')

    def test_authorized_user_gets_csv_for_current_organization_only(self):
        Client.objects.create(
            full_name='Іван Петренко',
            phone='+380501100001',
            email='ivan@example.com',
            organization=self.organization,
            created_by=self.user,
        )
        Client.objects.create(
            full_name='Чужий Клієнт',
            phone='+380501100002',
            email='external@example.com',
            organization=self.other_organization,
            created_by=self.other_user,
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse('client_export_csv'))
        csv_text = self._csv_text(response)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv; charset=utf-8')
        self.assertTrue(
            response['Content-Disposition'].startswith(
                'attachment; filename="clients_export_',
            )
        )
        self.assertIn('ID;ПІБ;Телефон;Email;Активний;Дата створення;Дата оновлення', csv_text)
        self.assertIn('Іван Петренко', csv_text)
        self.assertIn('ivan@example.com', csv_text)
        self.assertNotIn('Чужий Клієнт', csv_text)
        self.assertNotIn('external@example.com', csv_text)

    def test_client_export_respects_search_and_active_filters(self):
        Client.objects.create(
            full_name='Іван Активний',
            phone='+380501100003',
            is_active=True,
            organization=self.organization,
            created_by=self.user,
        )
        Client.objects.create(
            full_name='Іван Неактивний',
            phone='+380501100004',
            is_active=False,
            organization=self.organization,
            created_by=self.user,
        )
        Client.objects.create(
            full_name='Марія Активна',
            phone='+380501100005',
            is_active=True,
            organization=self.organization,
            created_by=self.user,
        )
        self.client.force_login(self.user)

        response = self.client.get(
            reverse('client_export_csv'),
            {'query': 'Іван', 'is_active': 'true'},
        )
        csv_text = self._csv_text(response)

        self.assertEqual(response.status_code, 200)
        self.assertIn('Іван Активний', csv_text)
        self.assertNotIn('Іван Неактивний', csv_text)
        self.assertNotIn('Марія Активна', csv_text)

    def test_unauthenticated_user_cannot_export_clients(self):
        response = self.client.get(reverse('client_export_csv'))

        self.assertEqual(response.status_code, 302)
        self.assertNotEqual(response.get('Content-Type'), 'text/csv; charset=utf-8')


class ClientAppointmentAccessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.organization = Organization.objects.create(name='History Org', slug='history-org')
        cls.other_organization = Organization.objects.create(name='Other History Org', slug='other-history-org')
        cls.admin = User.objects.create_user(
            username='history_admin', role=UserRole.ADMIN, organization=cls.organization,
        )
        cls.manager = User.objects.create_user(
            username='history_manager', role=UserRole.MANAGER, organization=cls.organization,
        )
        cls.employee = User.objects.create_user(
            username='history_employee', role=UserRole.EMPLOYEE, organization=cls.organization,
        )
        cls.colleague = User.objects.create_user(
            username='history_colleague', role=UserRole.EMPLOYEE, organization=cls.organization,
        )
        cls.unassigned_employee = User.objects.create_user(
            username='history_unassigned', role=UserRole.EMPLOYEE, organization=cls.organization,
        )
        cls.client_entity = Client.objects.create(
            full_name='Shared History Client', phone='+380501112211', organization=cls.organization,
        )
        cls.other_client = Client.objects.create(
            full_name='Foreign History Client', phone='+380501112212', organization=cls.other_organization,
        )
        category = ServiceCategory.objects.create(name='History Category', organization=cls.organization)
        service = Service.objects.create(
            name='History Service', category=category, price='100.00',
            duration_minutes=60, organization=cls.organization,
        )
        common = {
            'client': cls.client_entity, 'service': service, 'organization': cls.organization,
            'start_time': time(10), 'end_time': time(11),
        }
        cls.own_completed = Appointment.objects.create(
            employee=cls.employee, appointment_date=date(2026, 5, 1),
            status=AppointmentStatus.COMPLETED, actual_price='100.00', **common,
        )
        cls.own_planned = Appointment.objects.create(
            employee=cls.employee, appointment_date=date(2026, 5, 10), **common,
        )
        cls.colleague_completed = Appointment.objects.create(
            employee=cls.colleague, appointment_date=date(2026, 5, 20),
            status=AppointmentStatus.COMPLETED, actual_price='900.00', **common,
        )

    def test_employee_history_and_statistics_only_include_assigned_appointments(self):
        self.client.force_login(self.employee)

        response = self.client.get(reverse('client_detail', args=[self.client_entity.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            {item.pk for item in response.context['appointments']},
            {self.own_completed.pk, self.own_planned.pk},
        )
        self.assertEqual(response.context['total_count'], 2)
        self.assertEqual(response.context['completed_count'], 1)
        self.assertEqual(response.context['total_spent'], Decimal('100.00'))
        self.assertEqual(response.context['last_visit'], date(2026, 5, 1))
        self.assertNotContains(response, self.colleague.username)

    def test_history_filters_do_not_expand_access_or_change_visible_totals(self):
        self.client.force_login(self.employee)

        response = self.client.get(
            reverse('client_detail', args=[self.client_entity.pk]),
            {'status': AppointmentStatus.PLANNED, 'date_from': '2026-05-02'},
        )

        self.assertEqual([item.pk for item in response.context['appointments']], [self.own_planned.pk])
        self.assertEqual(response.context['total_count'], 2)
        self.assertEqual(response.context['completed_count'], 1)
        self.assertEqual(response.context['total_spent'], Decimal('100.00'))
        self.assertEqual(response.context['last_visit'], date(2026, 5, 1))

    def test_admin_and_manager_keep_complete_client_history_and_statistics(self):
        for user in (self.admin, self.manager):
            with self.subTest(role=user.role):
                self.client.force_login(user)
                response = self.client.get(reverse('client_detail', args=[self.client_entity.pk]))
                self.assertEqual(
                    {item.pk for item in response.context['appointments']},
                    {self.own_completed.pk, self.own_planned.pk, self.colleague_completed.pk},
                )
                self.assertEqual(response.context['total_count'], 3)
                self.assertEqual(response.context['completed_count'], 2)
                self.assertEqual(response.context['total_spent'], Decimal('1000.00'))
                self.assertEqual(response.context['last_visit'], date(2026, 5, 20))

    def test_employee_without_assignments_sees_empty_history_and_zero_totals(self):
        self.client.force_login(self.unassigned_employee)

        response = self.client.get(reverse('client_detail', args=[self.client_entity.pk]))

        self.assertEqual(list(response.context['appointments']), [])
        self.assertEqual(response.context['total_count'], 0)
        self.assertEqual(response.context['completed_count'], 0)
        self.assertEqual(response.context['total_spent'], 0)
        self.assertIsNone(response.context['last_visit'])

    def test_foreign_organization_client_is_not_accessible(self):
        for user in (self.employee, self.admin, self.manager):
            with self.subTest(role=user.role):
                self.client.force_login(user)
                response = self.client.get(reverse('client_detail', args=[self.other_client.pk]))
                self.assertEqual(response.status_code, 404)
