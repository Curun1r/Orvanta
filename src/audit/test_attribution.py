from datetime import date, time

from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, TestCase
from django.urls import reverse

from appointments.models import Appointment, AppointmentStatus
from clients.models import Client
from services_catalog.models import Service, ServiceCategory
from users.models import Organization, User, UserRole

from .context import audit_context, get_audit_context
from .models import AuditActionType, AuditEntityType, AuditLog


class AuditAttributionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.organization = Organization.objects.create(name='Attribution Org', slug='attribution-org')
        cls.other_organization = Organization.objects.create(name='Other Attribution Org', slug='other-attribution-org')
        cls.admin = User.objects.create_user(
            username='attribution_admin', role=UserRole.ADMIN, organization=cls.organization,
        )
        cls.manager = User.objects.create_user(
            username='attribution_manager', role=UserRole.MANAGER, organization=cls.organization,
        )
        cls.employee = User.objects.create_user(
            username='attribution_employee', role=UserRole.EMPLOYEE, organization=cls.organization,
        )
        cls.client_record = Client.objects.create(
            full_name='Audit Client', phone='+380501112233',
            organization=cls.organization, created_by=cls.admin,
        )
        cls.category = ServiceCategory.objects.create(name='Audit Category', organization=cls.organization)
        cls.service = Service.objects.create(
            name='Audit Service', category=cls.category, price='100.00', duration_minutes=60,
            organization=cls.organization,
        )
        cls.appointment = Appointment.objects.create(
            client=cls.client_record, service=cls.service, employee=cls.employee,
            created_by=cls.admin, organization=cls.organization,
            appointment_date=date(2026, 5, 10), start_time=time(10), end_time=time(11),
        )

    def setUp(self):
        AuditLog.objects.all().delete()

    def _log(self, action_type, entity_type, entity_id):
        return AuditLog.objects.get(
            action_type=action_type, entity_type=entity_type, entity_id=entity_id,
        )

    def _client_data(self, **overrides):
        data = {
            'full_name': 'Audit Client Edited', 'phone': self.client_record.phone,
            'email': '', 'birth_date': '', 'notes': 'Edited by manager', 'is_active': 'on',
        }
        data.update(overrides)
        return data

    def test_manager_edit_is_attributed_to_manager_instead_of_client_creator(self):
        self.client.force_login(self.manager)

        response = self.client.post(
            reverse('client_update', args=[self.client_record.pk]), self._client_data(),
            REMOTE_ADDR='192.0.2.25',
        )

        self.assertRedirects(response, reverse('client_list'))
        log = self._log(AuditActionType.UPDATE, AuditEntityType.CLIENT, self.client_record.pk)
        self.assertEqual(log.user, self.manager)
        self.assertEqual(log.organization, self.organization)
        self.client_record.refresh_from_db()
        self.assertEqual(self.client_record.created_by, self.admin)

    def test_http_client_creation_is_attributed_to_its_creator(self):
        self.client.force_login(self.manager)

        response = self.client.post(
            reverse('client_create'),
            self._client_data(full_name='New Audit Client', phone='+380501112234'),
        )

        self.assertRedirects(response, reverse('client_list'))
        created = Client.objects.get(phone='+380501112234')
        log = self._log(AuditActionType.CREATE, AuditEntityType.CLIENT, created.pk)
        self.assertEqual(log.user, self.manager)
        self.assertEqual(log.organization, self.organization)

    def test_service_creation_and_update_have_an_actor_without_created_by_field(self):
        self.client.force_login(self.manager)
        data = {
            'category': self.category.pk, 'name': 'New Audit Service', 'description': '',
            'price': '200.00', 'duration_minutes': 30, 'is_active': 'on',
        }

        response = self.client.post(reverse('service_create'), data)
        self.assertRedirects(response, reverse('service_list'))
        created = Service.objects.get(name='New Audit Service')
        self.assertEqual(
            self._log(AuditActionType.CREATE, AuditEntityType.SERVICE, created.pk).user,
            self.manager,
        )

        data['name'] = 'Renamed Audit Service'
        response = self.client.post(reverse('service_update', args=[created.pk]), data)
        self.assertRedirects(response, reverse('service_list'))
        self.assertEqual(
            self._log(AuditActionType.UPDATE, AuditEntityType.SERVICE, created.pk).user,
            self.manager,
        )

    def test_user_creation_and_role_edit_are_attributed_to_acting_admin(self):
        self.client.force_login(self.admin)

        response = self.client.post(reverse('user_create'), {
            'username': 'audit_new_employee', 'email': 'audit_new_employee@example.com',
            'password1': 'StrongPass123!', 'password2': 'StrongPass123!',
            'role': UserRole.EMPLOYEE,
        })

        self.assertRedirects(response, reverse('user_list'))
        created = User.objects.get(username='audit_new_employee')
        self.assertEqual(
            self._log(AuditActionType.CREATE, AuditEntityType.USER, created.pk).user,
            self.admin,
        )
        response = self.client.post(
            reverse('user_edit_role', args=[created.pk]), {'role': UserRole.MANAGER},
        )
        self.assertRedirects(response, reverse('user_list'))
        self.assertEqual(
            self._log(AuditActionType.UPDATE, AuditEntityType.USER, created.pk).user,
            self.admin,
        )

    def test_quick_status_and_price_changes_use_actual_actor(self):
        self.client.force_login(self.employee)
        response = self.client.post(reverse(
            'appointment_quick_status_update',
            args=[self.appointment.pk, AppointmentStatus.COMPLETED],
        ))
        self.assertRedirects(response, reverse('appointment_list'))
        log = self._log(AuditActionType.UPDATE, AuditEntityType.APPOINTMENT, self.appointment.pk)
        self.assertEqual(log.user, self.employee)

        self.client.force_login(self.manager)
        response = self.client.post(
            reverse('appointment_actual_price_update', args=[self.appointment.pk]),
            {'actual_price': '125.00'},
        )
        self.assertRedirects(response, reverse('appointment_list'))
        updates = AuditLog.objects.filter(
            action_type=AuditActionType.UPDATE, entity_type=AuditEntityType.APPOINTMENT,
            entity_id=self.appointment.pk,
        ).order_by('pk')
        self.assertEqual(list(updates.values_list('user_id', flat=True)), [self.employee.pk, self.manager.pk])

    def test_appointment_deletion_has_one_detailed_log_for_actual_deleting_admin(self):
        deleting_admin = User.objects.create_user(
            username='deleting_admin', role=UserRole.ADMIN, organization=self.organization,
        )
        self.client.force_login(deleting_admin)
        appointment_id = self.appointment.pk

        response = self.client.post(
            reverse('appointment_delete', args=[appointment_id]), REMOTE_ADDR='192.0.2.26',
        )

        self.assertRedirects(response, reverse('appointment_list'))
        self.assertFalse(Appointment.objects.filter(pk=appointment_id).exists())
        log = self._log(AuditActionType.DELETE, AuditEntityType.APPOINTMENT, appointment_id)
        self.assertEqual(log.user, deleting_admin)
        self.assertEqual(log.organization, self.organization)
        self.assertEqual(log.ip_address, '192.0.2.26')
        self.assertIn(f'Deleted appointment #{appointment_id}', log.description)
        self.assertIn(self.client_record.full_name, log.description)
        self.assertIn(self.service.name, log.description)

    def test_deleting_another_user_records_the_admin_without_recreating_target(self):
        target = User.objects.create_user(
            username='audit_deletion_target', role=UserRole.EMPLOYEE, organization=self.organization,
        )
        target_id = target.pk
        self.client.force_login(self.admin)

        response = self.client.post(reverse('user_delete', args=[target_id]), {'confirm': 'on'})

        self.assertRedirects(response, reverse('user_list'))
        self.assertFalse(User.objects.filter(pk=target_id).exists())
        log = self._log(AuditActionType.DELETE, AuditEntityType.USER, target_id)
        self.assertEqual(log.user, self.admin)
        self.assertEqual(log.organization, self.organization)

    def test_signup_create_is_attributed_to_newly_registered_user(self):
        response = self.client.post(reverse('signup'), {
            'username': 'audit_signup_owner', 'email': 'audit_signup@example.com',
            'password1': 'StrongPass123!', 'password2': 'StrongPass123!',
            'organization_name': 'Audit Signup Org',
        })

        self.assertRedirects(response, reverse('home'))
        created = User.objects.get(username='audit_signup_owner')
        log = self._log(AuditActionType.CREATE, AuditEntityType.USER, created.pk)
        self.assertEqual(log.user, created)
        self.assertEqual(log.organization, created.organization)

    def test_login_last_login_update_and_auth_event_identify_the_logged_in_user(self):
        self.admin.set_password('StrongPass123!')
        self.admin.save()
        AuditLog.objects.all().delete()

        response = self.client.post(reverse('login'), {
            'username': self.admin.username, 'password': 'StrongPass123!',
            'organization': self.organization.slug,
        })

        self.assertRedirects(response, reverse('home'))
        self.assertEqual(
            self._log(AuditActionType.UPDATE, AuditEntityType.USER, self.admin.pk).user,
            self.admin,
        )
        self.assertEqual(
            self._log(AuditActionType.LOGIN, AuditEntityType.AUTH, self.admin.pk).user,
            self.admin,
        )

    def test_sequential_requests_and_later_cli_save_do_not_share_actor(self):
        self.client.force_login(self.manager)
        self.client.post(reverse('client_update', args=[self.client_record.pk]), self._client_data())
        self.client.force_login(self.admin)
        self.client.post(reverse('client_update', args=[self.client_record.pk]), self._client_data())
        self.client_record.full_name = 'CLI update after HTTP'
        self.client_record.save()

        updates = AuditLog.objects.filter(
            action_type=AuditActionType.UPDATE, entity_type=AuditEntityType.CLIENT,
            entity_id=self.client_record.pk,
        ).order_by('pk')
        self.assertEqual(list(updates.values_list('user_id', flat=True)), [self.manager.pk, self.admin.pk, None])

    def test_cli_create_update_and_delete_do_not_claim_the_object_creator(self):
        created = Client.objects.create(
            full_name='CLI Client', phone='+380501112235',
            organization=self.organization, created_by=self.admin,
        )
        created.full_name = 'CLI Client Edited'
        created.save()
        client_id = created.pk
        created.delete()

        for action in (AuditActionType.CREATE, AuditActionType.UPDATE, AuditActionType.DELETE):
            with self.subTest(action=action):
                log = self._log(action, AuditEntityType.CLIENT, client_id)
                self.assertIsNone(log.user)
                self.assertEqual(log.organization, self.organization)

    def test_anonymous_request_does_not_claim_the_object_creator(self):
        request = RequestFactory().get('/')
        request.user = AnonymousUser()
        with audit_context(request=request):
            self.client_record.save()

        self.assertIsNone(
            self._log(AuditActionType.UPDATE, AuditEntityType.CLIENT, self.client_record.pk).user,
        )

    def test_explicit_context_can_attribute_non_http_work(self):
        with audit_context(user=self.manager):
            self.client_record.save()

        self.assertEqual(
            self._log(AuditActionType.UPDATE, AuditEntityType.CLIENT, self.client_record.pk).user,
            self.manager,
        )

    def test_nested_description_context_preserves_actor_and_resets_after_exception(self):
        temporary = Client.objects.create(
            full_name='Temporary Audit Client', phone='+380501112237',
            organization=self.organization,
        )
        client_id = temporary.pk
        with self.assertRaisesMessage(RuntimeError, 'test failure'):
            with audit_context(user=self.manager):
                with audit_context(description='Explicit audit event'):
                    temporary.delete()
                self.assertEqual(get_audit_context().user, self.manager)
                self.assertIsNone(get_audit_context().description)
                raise RuntimeError('test failure')

        log = self._log(AuditActionType.DELETE, AuditEntityType.CLIENT, client_id)
        self.assertEqual(log.user, self.manager)
        self.assertEqual(log.description, 'Explicit audit event')
        self.assertIsNone(get_audit_context().user)
        self.assertIsNone(get_audit_context().request)
        self.assertIsNone(get_audit_context().description)

    def test_entity_organization_is_preserved_when_actor_belongs_to_another_organization(self):
        other_client = Client.objects.create(
            full_name='Other Organization Client', phone='+380501112236',
            organization=self.other_organization,
        )
        with audit_context(user=self.admin):
            other_client.save()

        log = self._log(AuditActionType.UPDATE, AuditEntityType.CLIENT, other_client.pk)
        self.assertEqual(log.user, self.admin)
        self.assertEqual(log.organization, self.other_organization)

    def test_django_admin_service_change_records_global_staff_and_entity_organization(self):
        global_admin = User.objects.create_superuser(username='audit_global_staff')
        self.client.force_login(global_admin)

        response = self.client.post(
            reverse('admin:services_catalog_service_change', args=[self.service.pk]),
            {
                'organization': self.organization.pk, 'category': self.category.pk,
                'name': 'Service Changed Through Django Admin', 'description': '',
                'price': '150.00', 'duration_minutes': 60, 'is_active': 'on',
            },
        )

        self.assertRedirects(response, reverse('admin:services_catalog_service_changelist'))
        self.service.refresh_from_db()
        self.assertEqual(self.service.name, 'Service Changed Through Django Admin')
        log = self._log(AuditActionType.UPDATE, AuditEntityType.SERVICE, self.service.pk)
        self.assertEqual(log.user, global_admin)
        self.assertEqual(log.organization, self.organization)

    def test_bulk_deleting_acting_user_does_not_leave_invalid_audit_user_reference(self):
        actor = User.objects.create_user(
            username='bulk_deleted_actor', role=UserRole.ADMIN, organization=self.organization,
        )
        actor_id = actor.pk
        target = User.objects.create_user(
            username='bulk_deleted_target', role=UserRole.EMPLOYEE, organization=self.organization,
        )
        deleted_ids = [actor_id, target.pk]
        with audit_context(user=actor):
            User.objects.filter(pk__in=deleted_ids).delete()
            self.client_record.save()

        self.assertFalse(User.objects.filter(pk__in=deleted_ids).exists())
        logs = AuditLog.objects.filter(
            action_type=AuditActionType.DELETE, entity_type=AuditEntityType.USER,
            entity_id__in=deleted_ids,
        )
        self.assertEqual(logs.count(), 2)
        self.assertTrue(all(log.user_id is None for log in logs))
        self.assertTrue(all(log.organization == self.organization for log in logs))
        self.assertIsNone(
            self._log(AuditActionType.UPDATE, AuditEntityType.CLIENT, self.client_record.pk).user,
        )
