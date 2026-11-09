from django.test import TestCase
from django.urls import reverse

from users.models import Organization, User, UserRole

from .models import Service, ServiceCategory


class ServiceListPaginationTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name='Service Org', slug='service-org')
        self.other_organization = Organization.objects.create(
            name='Other Service Org',
            slug='other-service-org',
        )
        self.user = User.objects.create_user(
            username='service_manager',
            email='service_manager@example.com',
            password='StrongPass123!',
            role=UserRole.MANAGER,
            organization=self.organization,
        )
        self.category = ServiceCategory.objects.create(
            name='Service Category',
            organization=self.organization,
        )
        self.other_category = ServiceCategory.objects.create(
            name='Other Service Category',
            organization=self.other_organization,
        )

    def test_service_list_is_limited_to_page_size(self):
        for index in range(12):
            Service.objects.create(
                category=self.category,
                name=f'Service {index:02d}',
                price='100.00',
                duration_minutes=30,
                organization=self.organization,
            )
        self.client.force_login(self.user)

        response = self.client.get(reverse('service_list'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['page_obj']), 10)
        self.assertEqual(response.context['page_obj'].paginator.count, 12)

    def _csv_text(self, response):
        return response.content.decode('utf-8-sig')

    def test_service_export_contains_current_organization_services_only(self):
        Service.objects.create(
            category=self.category,
            name='Українська послуга',
            price='250.00',
            duration_minutes=45,
            organization=self.organization,
        )
        Service.objects.create(
            category=self.other_category,
            name='Чужа послуга',
            price='999.00',
            duration_minutes=30,
            organization=self.other_organization,
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse('service_export_csv'))
        csv_text = self._csv_text(response)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv; charset=utf-8')
        self.assertTrue(
            response['Content-Disposition'].startswith(
                'attachment; filename="services_export_',
            )
        )
        self.assertIn(
            'ID;Name;Category;Description;Base price;Duration, min;Active',
            csv_text,
        )
        self.assertIn('Українська послуга', csv_text)
        self.assertNotIn('Чужа послуга', csv_text)

    def test_service_export_respects_search_category_and_active_filters(self):
        second_category = ServiceCategory.objects.create(
            name='Second Service Category',
            organization=self.organization,
        )
        Service.objects.create(
            category=self.category,
            name='Масаж спини',
            description='Лікувальний масаж',
            price='500.00',
            duration_minutes=60,
            is_active=True,
            organization=self.organization,
        )
        Service.objects.create(
            category=self.category,
            name='Масаж рук',
            price='300.00',
            duration_minutes=30,
            is_active=False,
            organization=self.organization,
        )
        Service.objects.create(
            category=second_category,
            name='Масаж обличчя',
            price='450.00',
            duration_minutes=40,
            is_active=True,
            organization=self.organization,
        )
        Service.objects.create(
            category=self.category,
            name='Консультація',
            price='200.00',
            duration_minutes=20,
            is_active=True,
            organization=self.organization,
        )
        Service.objects.create(
            category=self.other_category,
            name='Масаж чужої організації',
            price='700.00',
            duration_minutes=60,
            is_active=True,
            organization=self.other_organization,
        )
        self.client.force_login(self.user)

        response = self.client.get(
            reverse('service_export_csv'),
            {
                'query': 'Масаж',
                'category': self.category.pk,
                'is_active': 'true',
            },
        )
        csv_text = self._csv_text(response)

        self.assertEqual(response.status_code, 200)
        self.assertIn('Масаж спини', csv_text)
        self.assertNotIn('Масаж рук', csv_text)
        self.assertNotIn('Масаж обличчя', csv_text)
        self.assertNotIn('Консультація', csv_text)
        self.assertNotIn('Масаж чужої організації', csv_text)

    def test_unauthenticated_user_cannot_export_services(self):
        response = self.client.get(reverse('service_export_csv'))

        self.assertEqual(response.status_code, 302)
        self.assertNotEqual(response.get('Content-Type'), 'text/csv; charset=utf-8')
