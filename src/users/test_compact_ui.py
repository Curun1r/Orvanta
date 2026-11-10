from django.test import Client, TestCase
from django.urls import reverse

from .models import Organization, User, UserRole


class CompactUiPreferenceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        organization = Organization.objects.create(name='Compact UI Org', slug='compact-ui-org')
        cls.user = User.objects.create_user(
            username='compact_employee', organization=organization, role=UserRole.EMPLOYEE,
        )
        cls.colleague = User.objects.create_user(
            username='compact_colleague', organization=organization, role=UserRole.MANAGER,
        )

    def setUp(self):
        self.client.force_login(self.user)
        self.url = reverse('toggle_compact_ui')

    def test_toggling_changes_only_own_preference_and_preserves_return_query(self):
        target = reverse('profile') + '?tab=interface'
        for expected in (True, False):
            response = self.client.post(self.url, {
                'next': target, 'user_id': self.colleague.pk,
            })
            self.assertRedirects(response, target)
            self.user.refresh_from_db()
            self.colleague.refresh_from_db()
            self.assertEqual(self.user.hide_section_subtitles, expected)
            self.assertFalse(self.colleague.hide_section_subtitles)

    def test_missing_blank_or_unsafe_return_urls_fall_back_to_profile(self):
        for target in (
            None, '', '   ', 'https://example.invalid/phishing',
            '//example.invalid/phishing', '///example.invalid/phishing',
            r'\\example.invalid/phishing', 'https://testserver@example.invalid/',
            'javascript:alert(1)', 'https://[invalid/',
        ):
            with self.subTest(target=target):
                self.user.refresh_from_db()
                previous = self.user.hide_section_subtitles
                data = {} if target is None else {'next': target}
                response = self.client.post(self.url, data)
                self.assertRedirects(response, reverse('profile'))
                self.user.refresh_from_db()
                self.assertEqual(self.user.hide_section_subtitles, not previous)

    def test_same_host_absolute_return_url_is_allowed(self):
        target = 'http://testserver/profile/?tab=interface'
        response = self.client.post(self.url, {'next': target})
        self.assertRedirects(response, target, fetch_redirect_response=False)

    def test_secure_request_rejects_http_downgrade(self):
        for target, expected in (
            ('http://testserver/profile/', reverse('profile')),
            ('//testserver/profile/', reverse('profile')),
            ('https://testserver/profile/', 'https://testserver/profile/'),
        ):
            with self.subTest(target=target):
                response = self.client.post(self.url, {'next': target}, secure=True)
                self.assertRedirects(response, expected, fetch_redirect_response=False)

    def test_requires_authenticated_post(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)
        self.client.logout()
        response = self.client.post(self.url, {'next': reverse('profile')})
        self.assertRedirects(response, f'{reverse("login")}?next={self.url}')
        self.user.refresh_from_db()
        self.assertFalse(self.user.hide_section_subtitles)

    def test_requires_csrf_token(self):
        protected_client = Client(enforce_csrf_checks=True)
        protected_client.force_login(self.user)
        response = protected_client.post(self.url, {'next': reverse('profile')})
        self.assertEqual(response.status_code, 403)
        self.user.refresh_from_db()
        self.assertFalse(self.user.hide_section_subtitles)
