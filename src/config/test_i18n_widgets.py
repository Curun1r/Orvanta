from datetime import date, time
from decimal import Decimal
from html.parser import HTMLParser

from django.conf import settings
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import translation
from django.utils.translation import override

from appointments.forms import AppointmentFilterForm, AppointmentForm
from appointments.models import Appointment, AppointmentStatus
from audit.forms import AuditLogFilterForm
from clients.forms import ClientForm
from clients.models import Client
from services_catalog.models import Service, ServiceCategory
from users.models import Organization, User, UserRole

from .forms import FinanceAnalyticsFilterForm


class InputValues(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.values = {}
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'input' and attrs.get('name'):
            self.values[attrs['name']] = attrs


class DateWidgetLanguageTests(SimpleTestCase):
    def test_native_date_widgets_render_iso_values_in_both_languages(self):
        day = date(2026, 11, 9)
        for language in ('en', 'uk'):
            with self.subTest(language=language), override(language):
                forms_and_fields = (
                    (AppointmentForm(instance=Appointment(appointment_date=day)), ('appointment_date',)),
                    (AppointmentFilterForm(initial={'appointment_date': day}), ('appointment_date',)),
                    (ClientForm(instance=Client(birth_date=day)), ('birth_date',)),
                    (FinanceAnalyticsFilterForm(initial={'date_from': day, 'date_to': day}), ('date_from', 'date_to')),
                    (AuditLogFilterForm(initial={'date_from': day, 'date_to': day}), ('date_from', 'date_to')),
                )
                for form, fields in forms_and_fields:
                    for field in fields:
                        with self.subTest(form=type(form).__name__, field=field):
                            attrs = InputValues(form[field].as_widget()).values[field]
                            self.assertEqual(attrs['type'], 'date')
                            self.assertEqual(attrs['value'], '2026-11-09')


class AppointmentWidgetRoundTripTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.organization = Organization.objects.create(name='Widget Org', slug='widget-org')
        cls.admin = User.objects.create_user(
            username='widget_admin', role=UserRole.ADMIN, organization=cls.organization,
        )
        cls.employee = User.objects.create_user(
            username='widget_employee', role=UserRole.EMPLOYEE, organization=cls.organization,
        )
        cls.client_record = Client.objects.create(
            full_name='Widget Client', phone='+380501112244', organization=cls.organization,
        )
        category = ServiceCategory.objects.create(name='Widget Category', organization=cls.organization)
        cls.service = Service.objects.create(
            name='Widget Service', category=category, price='1250.50', duration_minutes=60,
            organization=cls.organization,
        )
        cls.appointment = Appointment.objects.create(
            client=cls.client_record, service=cls.service, employee=cls.employee,
            organization=cls.organization, created_by=cls.admin,
            appointment_date=date(2026, 11, 9), start_time=time(10), end_time=time(11),
            actual_price=Decimal('1250.50'),
        )

    def setUp(self):
        self.addCleanup(translation.deactivate)
        self.client.force_login(self.admin)

    def test_inline_price_renders_a_decimal_point_and_round_trips_in_both_languages(self):
        for language in ('en', 'uk'):
            with self.subTest(language=language):
                self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = language
                response = self.client.get(reverse('appointment_list'))
                attrs = InputValues(response.content.decode()).values['actual_price']
                self.assertEqual(attrs['type'], 'number')
                self.assertEqual(attrs['value'], '1250.50')

                saved = self.client.post(
                    reverse('appointment_actual_price_update', args=[self.appointment.pk]),
                    {'actual_price': attrs['value']},
                )
                self.assertRedirects(saved, reverse('appointment_list'))
                self.appointment.refresh_from_db()
                self.assertEqual(self.appointment.actual_price, Decimal('1250.50'))

    def test_editing_an_appointment_preserves_its_date_and_price_in_both_languages(self):
        url = reverse('appointment_update', args=[self.appointment.pk])
        for language in ('en', 'uk'):
            with self.subTest(language=language):
                self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = language
                response = self.client.get(url)
                inputs = InputValues(response.content.decode()).values
                self.assertEqual(inputs['appointment_date']['value'], '2026-11-09')
                self.assertEqual(inputs['actual_price']['value'], '1250.50')
                saved = self.client.post(url, {
                    'client': self.client_record.pk, 'service': self.service.pk,
                    'employee': self.employee.pk, 'appointment_date': inputs['appointment_date']['value'],
                    'start_time': inputs['start_time']['value'], 'end_time': inputs['end_time']['value'],
                    'actual_price': inputs['actual_price']['value'], 'status': AppointmentStatus.PLANNED,
                    'comment': '',
                })
                self.assertRedirects(saved, reverse('appointment_list'))
                self.appointment.refresh_from_db()
                self.assertEqual(self.appointment.appointment_date, date(2026, 11, 9))
                self.assertEqual(self.appointment.actual_price, Decimal('1250.50'))
