from datetime import date, time

from django.conf import settings
from django.test import Client as HttpClient, TestCase, override_settings
from django.urls import reverse
from django.utils import translation
from django.utils.translation import override

from appointments.forms import AppointmentForm
from appointments.models import Appointment, AppointmentStatus
from clients.models import Client
from services_catalog.models import Service, ServiceCategory
from users.models import Organization, User, UserRole


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class LanguagePreferenceTests(TestCase):
    def setUp(self):
        self.addCleanup(translation.deactivate)

    @classmethod
    def setUpTestData(cls):
        cls.organization = Organization.objects.create(name='Language Org', slug='language-org')
        cls.admin = User.objects.create_user(
            username='language_admin', password='StrongPass123!',
            organization=cls.organization, role=UserRole.ADMIN,
        )
        cls.employee = User.objects.create_user(
            username='language_employee', organization=cls.organization,
            role=UserRole.EMPLOYEE,
        )
        cls.client_record = Client.objects.create(
            full_name='Марія / Maria', phone='+380501112233',
            organization=cls.organization, created_by=cls.admin,
        )
        category = ServiceCategory.objects.create(name='User category', organization=cls.organization)
        cls.service = Service.objects.create(
            name='Послуга користувача', category=category, price='150.00',
            duration_minutes=60, organization=cls.organization,
        )
        cls.appointment = Appointment.objects.create(
            client=cls.client_record, service=cls.service, employee=cls.employee,
            organization=cls.organization, created_by=cls.admin,
            appointment_date=date(2026, 11, 9), start_time=time(10), end_time=time(11),
        )

    def test_first_visit_defaults_to_english_even_for_a_ukrainian_browser(self):
        response = self.client.get(reverse('login'), HTTP_ACCEPT_LANGUAGE='uk,en;q=0.5')

        self.assertEqual(settings.LANGUAGE_CODE, 'en')
        self.assertEqual(response.headers['Content-Language'], 'en')
        self.assertContains(response, '<html lang="en">')
        self.assertContains(response, 'name="language" value="uk"')
        self.assertContains(response, 'Username')
        self.assertNotContains(response, 'Вхід до Orvanta')

    def test_language_choice_survives_navigation_and_retains_the_return_url(self):
        target = reverse('login') + '?next=/appointments/'
        response = self.client.post(reverse('set_language'), {'language': 'uk', 'next': target})

        self.assertRedirects(response, target, fetch_redirect_response=False)
        self.assertEqual(response.cookies[settings.LANGUAGE_COOKIE_NAME].value, 'uk')
        login = self.client.get(target)
        signup = self.client.get(reverse('signup'))
        self.assertContains(login, '<html lang="uk">')
        self.assertContains(login, 'Вхід до Orvanta')
        self.assertEqual(signup.headers['Content-Language'], 'uk')
        self.assertIn('Cookie', login.headers.get('Vary', ''))

        self.client.post(reverse('set_language'), {'language': 'en', 'next': target})
        self.assertContains(self.client.get(target), '<html lang="en">')

    def test_invalid_language_cookie_falls_back_to_english(self):
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = 'unsupported'
        response = self.client.get(reverse('login'), HTTP_ACCEPT_LANGUAGE='uk')
        self.assertEqual(response.headers['Content-Language'], 'en')

    def test_language_selection_rejects_external_return_url_and_requires_csrf(self):
        protected_client = HttpClient(enforce_csrf_checks=True)
        self.assertEqual(protected_client.post(
            reverse('set_language'), {'language': 'uk', 'next': '/login/'},
        ).status_code, 403)
        response = self.client.post(reverse('set_language'), {
            'language': 'uk', 'next': 'https://example.invalid/phishing',
        })
        self.assertEqual(response.status_code, 302)
        self.assertFalse(response['Location'].startswith('https://example.invalid'))

    def test_switching_language_preserves_the_session_and_business_records(self):
        self.client.force_login(self.admin)
        before = list(Appointment.objects.values())
        self.client.post(reverse('set_language'), {'language': 'uk', 'next': '/'})
        ukrainian = self.client.get(reverse('home'))
        self.assertContains(ukrainian, 'Головна')
        self.assertEqual(int(self.client.session['_auth_user_id']), self.admin.pk)
        self.client.post(reverse('set_language'), {'language': 'en', 'next': '/'})
        english = self.client.get(reverse('home'))
        self.assertContains(english, 'Home')
        self.assertEqual(list(Appointment.objects.values()), before)
        self.client_record.refresh_from_db()
        self.assertEqual(self.client_record.full_name, 'Марія / Maria')
        self.service.refresh_from_db()
        self.assertEqual(self.service.name, 'Послуга користувача')

    def test_model_labels_and_form_fields_are_evaluated_in_the_current_language(self):
        for language, role_label, status_label, client_label in (
            ('en', 'Employee', 'Planned', 'Client'),
            ('uk', 'Співробітник', 'Заплановано', 'Клієнт'),
        ):
            with self.subTest(language=language), override(language):
                self.assertEqual(self.employee.get_role_display(), role_label)
                self.assertEqual(self.appointment.get_status_display(), status_label)
                form = AppointmentForm(organization=self.organization)
                self.assertEqual(str(form.fields['client'].label), client_label)

    def test_javascript_catalog_uses_the_selected_language_and_varies_by_cookie(self):
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = 'uk'
        response = self.client.get(reverse('javascript-catalog'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['Content-Language'], 'uk')
        self.assertIn('Cookie', response.headers.get('Vary', ''))
        self.assertContains(response, 'Show')
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = 'en'
        self.assertEqual(self.client.get(reverse('javascript-catalog')).headers['Content-Language'], 'en')

    def test_language_switch_does_not_bypass_employee_appointment_permissions(self):
        colleague = User.objects.create_user(
            username='language_colleague', role=UserRole.EMPLOYEE, organization=self.organization,
        )
        hidden = Appointment.objects.create(
            client=self.client_record, service=self.service, employee=colleague,
            organization=self.organization, appointment_date=date(2026, 11, 10),
            start_time=time(10), end_time=time(11),
        )
        self.client.force_login(self.employee)
        for language in ('en', 'uk'):
            with self.subTest(language=language):
                self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = language
                records = self.client.get('/api/appointments/').json()
                self.assertEqual([item['id'] for item in records], [self.appointment.pk])
                self.assertEqual(self.client.get(f'/api/appointments/{hidden.pk}/').status_code, 404)
