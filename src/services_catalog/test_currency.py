import csv
from datetime import date, time
from decimal import Decimal
from io import StringIO

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from api.serializers import AppointmentSerializer, ServiceSerializer
from appointments.forms import AppointmentForm
from appointments.models import Appointment, AppointmentStatus
from clients.models import Client
from users.models import Organization, User, UserRole

from .currencies import Currency
from .forms import ServiceForm
from .models import Service, ServiceCategory


class ServiceCurrencyTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.organization = Organization.objects.create(name='Currency Studio', slug='currency-studio')
        cls.manager = User.objects.create_user(
            username='currency_manager', organization=cls.organization, role=UserRole.MANAGER,
        )
        cls.employee = User.objects.create_user(
            username='currency_employee', organization=cls.organization, role=UserRole.EMPLOYEE,
        )
        cls.category = ServiceCategory.objects.create(name='Care', organization=cls.organization)
        cls.client_record = Client.objects.create(
            full_name='Emma Wilson', phone='+353000000001',
            organization=cls.organization, created_by=cls.manager,
        )
        cls.euro_service = Service.objects.create(
            name='Euro massage', currency=Currency.EUR, price='29.50', duration_minutes=30,
            category=cls.category, organization=cls.organization,
        )
        cls.dollar_service = Service.objects.create(
            name='Dollar massage', currency=Currency.USD, price='45.00', duration_minutes=30,
            category=cls.category, organization=cls.organization,
        )

    def setUp(self):
        self.client.force_login(self.manager)

    def service_data(self, **overrides):
        return {
            'category': self.category.pk, 'name': 'Consultation', 'description': '',
            'currency': Currency.EUR, 'price': '35.25', 'duration_minutes': 30,
            'is_active': True, **overrides,
        }

    def appointment_data(self, **overrides):
        return {
            'client': self.client_record.pk, 'service': self.euro_service.pk,
            'employee': self.employee.pk, 'appointment_date': '2026-12-15',
            'start_time': '10:00', 'end_time': '10:30', 'actual_price': '29.50',
            'status': AppointmentStatus.PLANNED, **overrides,
        }

    def make_appointment(self):
        return Appointment.objects.create(
            client=self.client_record, service=self.euro_service, employee=self.employee,
            organization=self.organization, created_by=self.manager,
            appointment_date=date(2026, 12, 15), start_time=time(10), end_time=time(10, 30),
            actual_price='29.50',
        )

    def test_existing_default_remains_hryvnia_and_keeps_numeric_price(self):
        service = Service.objects.create(
            name='Legacy-style service', price='500.00', duration_minutes=30,
            organization=self.organization,
        )
        service.refresh_from_db()
        self.assertEqual(service.currency, Currency.UAH)
        self.assertEqual(service.price, Decimal('500.00'))

    def test_new_services_store_selected_currency_without_conversion(self):
        for currency in (Currency.EUR, Currency.USD):
            with self.subTest(currency=currency):
                response = self.client.post(reverse('service_create'), self.service_data(
                    name=f'{currency} consultation', currency=currency,
                ))
                self.assertRedirects(response, reverse('service_list'))
                service = Service.objects.get(name=f'{currency} consultation')
                self.assertEqual(service.currency, currency)
                self.assertEqual(service.price, Decimal('35.25'))

    def test_invalid_currency_is_rejected_and_selector_precedes_price(self):
        response = self.client.post(reverse('service_create'), self.service_data(currency='GBP'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('currency', response.context['form'].errors)
        self.assertFalse(Service.objects.filter(name='Consultation').exists())
        fields = list(ServiceForm(organization=self.organization).fields)
        self.assertLess(fields.index('currency'), fields.index('price'))

    def test_forged_edit_cannot_change_currency_but_can_change_price(self):
        response = self.client.post(
            reverse('service_update', args=[self.euro_service.pk]),
            self.service_data(name=self.euro_service.name, currency=Currency.USD, price='40.00'),
        )
        self.assertRedirects(response, reverse('service_list'))
        self.euro_service.refresh_from_db()
        self.assertEqual(self.euro_service.currency, Currency.EUR)
        self.assertEqual(self.euro_service.price, Decimal('40.00'))

    def test_model_rejects_currency_changes_and_database_rejects_unsupported_codes(self):
        self.euro_service.currency = Currency.USD
        with self.assertRaises(ValidationError):
            self.euro_service.save()
        self.euro_service.refresh_from_db()
        self.assertEqual(self.euro_service.currency, Currency.EUR)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Service.objects.filter(pk=self.euro_service.pk).update(currency='GBP')

    def test_service_currency_reaches_pages_csv_and_api(self):
        for service in (self.euro_service, self.dollar_service):
            with self.subTest(currency=service.currency):
                price = f'{Decimal(service.price):.2f}'
                response = self.client.get(reverse('service_detail', args=[service.pk]))
                self.assertContains(response, f'{price} {service.currency}')
                serialized = ServiceSerializer(service).data
                self.assertEqual(serialized['currency'], service.currency)
                self.assertEqual(serialized['price'], price)
        response = self.client.get(reverse('service_export_csv'))
        rows = list(csv.reader(StringIO(response.content.decode('utf-8-sig')), delimiter=';'))
        self.assertEqual(rows[0][-1], 'Currency')
        self.assertEqual({row[-1] for row in rows[1:]}, {'EUR', 'USD'})

    def test_appointment_choices_and_actual_price_show_service_currency(self):
        appointment = self.make_appointment()
        form = AppointmentForm(instance=appointment, organization=self.organization)
        self.assertEqual(str(form.fields['actual_price'].label), 'Actual price (EUR)')
        labels = [str(label) for _key, label in form.fields['service'].choices]
        self.assertIn('Euro massage — 29.50 EUR', labels)
        self.assertIn('Dollar massage — 45.00 USD', labels)
        response = self.client.get(reverse('appointment_detail', args=[appointment.pk]))
        self.assertContains(response, '29.50 EUR')
        self.assertEqual(AppointmentSerializer(appointment).data['currency'], 'EUR')

    def test_priced_appointment_cannot_silently_switch_currency(self):
        appointment = self.make_appointment()
        form = AppointmentForm(
            data=self.appointment_data(service=self.dollar_service.pk),
            instance=appointment, organization=self.organization,
        )
        self.assertFalse(form.is_valid())
        self.assertIn('service', form.errors)
        appointment.refresh_from_db()
        self.assertEqual(appointment.service_id, self.euro_service.pk)
        self.assertEqual(appointment.actual_price, Decimal('29.50'))

        cleared = AppointmentForm(
            data=self.appointment_data(service=self.dollar_service.pk, actual_price=''),
            instance=appointment, organization=self.organization,
        )
        self.assertTrue(cleared.is_valid(), cleared.errors)
        cleared.save()
        appointment.refresh_from_db()
        self.assertEqual(appointment.service_id, self.dollar_service.pk)
        self.assertIsNone(appointment.actual_price)
