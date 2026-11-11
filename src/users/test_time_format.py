from datetime import datetime, time, timezone as datetime_timezone

from django.template import Context, Template
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import formats, timezone, translation

from .context_processors import workspace_preferences
from .models import Organization, OrganizationTimeFormat, User, UserRole


class OrganizationTimeFormatTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.organization = Organization.objects.create(name='Clock Workspace', slug='clock-workspace')
        cls.other_organization = Organization.objects.create(
            name='Other Clock Workspace', slug='other-clock-workspace', time_format='12',
        )
        cls.admin = User.objects.create_user(
            username='clock_admin', organization=cls.organization, role=UserRole.ADMIN,
        )
        cls.manager = User.objects.create_user(
            username='clock_manager', organization=cls.organization, role=UserRole.MANAGER,
        )
        cls.employee = User.objects.create_user(
            username='clock_employee', organization=cls.organization, role=UserRole.EMPLOYEE,
        )
        cls.other_admin = User.objects.create_user(
            username='other_clock_admin', organization=cls.other_organization, role=UserRole.ADMIN,
        )

    def test_existing_workspace_defaults_to_24_hour_display(self):
        self.assertEqual(self.organization.time_format, OrganizationTimeFormat.TWENTY_FOUR_HOUR)
        self.client.force_login(self.admin)
        response = self.client.get(reverse('organization_settings'))
        self.assertContains(response, 'name="time_format"')
        self.assertContains(response, '<option value="24" selected>24-hour (14:30)</option>', html=True)
        self.assertEqual(response.context['workspace_time_format'], '24')

    def test_admin_can_select_12_hour_and_older_name_only_posts_preserve_it(self):
        self.client.force_login(self.admin)
        stored_date = self.organization.created_at
        response = self.client.post(reverse('organization_settings'), {
            'name': self.organization.name, 'time_format': '12',
        }, follow=True)
        self.assertRedirects(response, reverse('organization_settings'))
        self.organization.refresh_from_db()
        self.assertEqual(self.organization.time_format, '12')
        self.assertEqual(self.organization.created_at, stored_date)
        self.assertTrue(response.context['workspace_hour12'])

        response = self.client.post(reverse('organization_settings'), {
            'name': 'Clock Workspace Renamed',
        })
        self.assertRedirects(response, reverse('organization_settings'))
        self.organization.refresh_from_db()
        self.assertEqual(self.organization.time_format, '12')
        self.assertEqual(self.organization.name, 'Clock Workspace Renamed')

    def test_invalid_time_format_does_not_change_workspace(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse('organization_settings'), {
            'name': 'Rejected Rename', 'time_format': '13',
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('time_format', response.context['form'].errors)
        self.organization.refresh_from_db()
        self.assertEqual(self.organization.time_format, '24')
        self.assertEqual(self.organization.name, 'Clock Workspace')

    def test_manager_and_employee_cannot_change_time_format(self):
        for user in (self.manager, self.employee):
            with self.subTest(role=user.role):
                self.client.force_login(user)
                response = self.client.post(reverse('organization_settings'), {
                    'name': self.organization.name, 'time_format': '12',
                })
                self.assertRedirects(response, reverse('home'))
                self.organization.refresh_from_db()
                self.assertEqual(self.organization.time_format, '24')

    def test_preferences_are_isolated_between_organizations(self):
        factory = RequestFactory()
        for user, expected in ((self.admin, '24'), (self.other_admin, '12'), (self.admin, '24')):
            request = factory.get('/')
            request.user = user
            preferences = workspace_preferences(request)
            self.assertEqual(preferences['workspace_time_format'], expected)
            result = Template(
                '{% load workspace_formats %}{{ value|workspace_time:workspace_time_format }}',
            ).render(Context({'value': time(14, 30), **preferences}))
            self.assertEqual(result, '14:30' if expected == '24' else '2:30 PM')

    def test_timestamp_formats_keep_timezone_and_localized_date(self):
        stamp = datetime(2026, 11, 11, 12, 30, tzinfo=datetime_timezone.utc)
        template = Template(
            '{% load workspace_formats %}{{ value|workspace_datetime:preference }}',
        )
        with timezone.override('Europe/Kyiv'):
            for language, afternoon in (('en', 'PM'), ('uk', 'після полудня')):
                with self.subTest(language=language), translation.override(language):
                    date = formats.date_format(timezone.localtime(stamp), 'SHORT_DATE_FORMAT')
                    self.assertEqual(template.render(Context({
                        'value': stamp, 'preference': '24',
                    })), f'{date} 14:30')
                    self.assertEqual(template.render(Context({
                        'value': stamp, 'preference': '12',
                    })), f'{date} 2:30 {afternoon}')

    def test_midnight_and_noon_remain_distinct_in_12_hour_display(self):
        template = Template('{% load workspace_formats %}{{ value|workspace_time:"12" }}')
        self.assertEqual(template.render(Context({'value': time(0, 5)})), '12:05 AM')
        self.assertEqual(template.render(Context({'value': time(12, 5)})), '12:05 PM')
