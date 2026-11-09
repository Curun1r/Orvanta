from django.db import IntegrityError
from django.test import TestCase

from .models import Organization, User, UserRole


class OrganizationModelTests(TestCase):
    def test_str_returns_name(self):
        org = Organization(name='Тестова організація', slug='test-org')
        self.assertEqual(str(org), 'Тестова організація')

    def test_slug_must_be_unique(self):
        Organization.objects.create(name='Перша', slug='unique-slug')
        with self.assertRaises(IntegrityError):
            Organization.objects.create(name='Друга', slug='unique-slug')

    def test_name_must_be_unique(self):
        Organization.objects.create(name='Одна назва', slug='slug-1')
        with self.assertRaises(IntegrityError):
            Organization.objects.create(name='Одна назва', slug='slug-2')

    def test_ordering_is_by_name(self):
        Organization.objects.create(name='Б Організація', slug='b-org')
        Organization.objects.create(name='А Організація', slug='a-org')
        names = list(
            Organization.objects.filter(slug__in=['a-org', 'b-org'])
            .values_list('name', flat=True)
        )
        self.assertEqual(names, ['А Організація', 'Б Організація'])


class UserModelTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='Тест Орг', slug='test-org')

    def test_str_shows_username_and_role(self):
        user = User(username='john', role=UserRole.ADMIN)
        self.assertEqual(str(user), 'john (Administrator)')

    def test_default_role_is_employee(self):
        user = User.objects.create_user(username='emp', password='pass123')
        self.assertEqual(user.role, UserRole.EMPLOYEE)

    def test_role_choices_are_correct(self):
        choices = [c[0] for c in UserRole.choices]
        self.assertIn('admin', choices)
        self.assertIn('manager', choices)
        self.assertIn('employee', choices)

    def test_user_can_be_linked_to_organization(self):
        user = User.objects.create_user(
            username='admin_user',
            password='pass123',
            organization=self.org,
            role=UserRole.ADMIN,
        )
        self.assertEqual(user.organization, self.org)
        self.assertIn(user, self.org.users.all())

    def test_user_organization_nullable(self):
        user = User.objects.create_user(username='noorg', password='pass123')
        self.assertIsNone(user.organization)

    def test_str_manager_role(self):
        user = User(username='mgr', role=UserRole.MANAGER)
        self.assertEqual(str(user), 'mgr (Manager)')

    def test_str_employee_role(self):
        user = User(username='emp', role=UserRole.EMPLOYEE)
        self.assertEqual(str(user), 'emp (Employee)')
