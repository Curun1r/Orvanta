import re
from collections import defaultdict
from datetime import date, datetime, timedelta
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from appointments.models import Appointment, AppointmentStatus, AppointmentStatusHistory
from audit.models import AuditLog
from clients.models import Client
from services_catalog.models import Service, ServiceCategory

from .models import Organization, User, UserRole


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class DemoSetupTests(TestCase):
    password = 'StrongDemoPass2026!'
    usernames = {
        'demo_admin': UserRole.ADMIN,
        'demo_manager': UserRole.MANAGER,
        'demo_emma': UserRole.EMPLOYEE,
        'demo_olivia': UserRole.EMPLOYEE,
        'demo_james': UserRole.EMPLOYEE,
        'demo_sophie': UserRole.EMPLOYEE,
        'demo_daniel': UserRole.EMPLOYEE,
    }

    def _setup_demo(self, **options):
        output = StringIO()
        options.setdefault('password', self.password)
        call_command('setup_demo', stdout=output, **options)
        return output.getvalue()

    def _snapshot(self):
        """Capture stored rows, including passwords and generated primary keys."""
        return {
            model._meta.label: list(model.objects.order_by('pk').values())
            for model in (
                Organization, User, Client, ServiceCategory, Service,
                Appointment, AppointmentStatusHistory, AuditLog,
            )
        }

    def _other_workspace(self):
        org = Organization.objects.create(name='Real Business', slug='real-business')
        owner = User.objects.create_user(
            username='real_owner', organization=org, role=UserRole.ADMIN,
        )
        employee = User.objects.create_user(
            username='real_employee', organization=org, role=UserRole.EMPLOYEE,
        )
        client = Client.objects.create(
            full_name='Real Client', phone='+380501000001',
            organization=org, created_by=owner,
        )
        category = ServiceCategory.objects.create(name='Real Category', organization=org)
        service = Service.objects.create(
            name='Real Service', category=category, price='120.00', duration_minutes=60,
            organization=org,
        )
        appointment = Appointment.objects.create(
            client=client, service=service, employee=employee, created_by=owner,
            organization=org, appointment_date=date(2026, 6, 15),
            start_time='09:00', end_time='10:00',
        )
        return org, owner, employee, client, service, appointment

    def test_clean_database_gets_complete_demo_workspace_and_login_for_every_role(self):
        existing_organizations = list(Organization.objects.order_by('pk').values())
        self._setup_demo()

        org = Organization.objects.get(slug='orvanta-demo')
        self.assertTrue(org.is_demo)
        self.assertEqual(org.name, 'Orvanta Demo')
        self.assertEqual(Organization.objects.count(), len(existing_organizations) + 1)
        self.assertEqual(
            list(Organization.objects.exclude(pk=org.pk).order_by('pk').values()),
            existing_organizations,
        )
        self.assertEqual(ServiceCategory.objects.filter(organization=org).count(), 5)
        self.assertEqual(Service.objects.filter(organization=org).count(), 30)
        self.assertEqual(Client.objects.filter(organization=org).count(), 35)
        self.assertEqual(Appointment.objects.filter(organization=org).count(), 180)
        self.assertEqual(
            dict(User.objects.filter(organization=org).values_list('username', 'role')),
            self.usernames,
        )
        for username, role in self.usernames.items():
            with self.subTest(username=username):
                user = User.objects.get(username=username)
                self.assertTrue(user.is_active)
                self.assertFalse(user.is_staff)
                self.assertFalse(user.is_superuser)
                self.assertEqual(user.role, role)
                self.assertTrue(user.check_password(self.password))

        for username in ('demo_admin', 'demo_manager', 'demo_emma'):
            with self.subTest(login=username):
                self.client.logout()
                response = self.client.post(reverse('login'), {
                    'username': username, 'password': self.password,
                    'organization': org.slug,
                })
                self.assertRedirects(response, reverse('home'))
                self.assertEqual(int(self.client.session['_auth_user_id']), User.objects.get(username=username).pk)

    def test_demo_appointments_are_relative_use_service_duration_and_do_not_overlap(self):
        today = timezone.localdate()
        self._setup_demo()
        appointments = list(Appointment.objects.select_related('service', 'employee', 'client'))

        self.assertTrue(any(item.appointment_date == today for item in appointments))
        self.assertTrue(any(item.appointment_date > today for item in appointments))
        self.assertTrue(any(item.status == AppointmentStatus.COMPLETED and item.actual_price is not None for item in appointments))
        self.assertTrue(any(item.status == AppointmentStatus.COMPLETED and item.actual_price is None for item in appointments))
        self.assertTrue(any(item.status == AppointmentStatus.CANCELLED for item in appointments))
        slots = defaultdict(list)
        for item in appointments:
            self.assertEqual(item.client.organization_id, item.organization_id)
            self.assertEqual(item.service.organization_id, item.organization_id)
            self.assertEqual(item.employee.organization_id, item.organization_id)
            duration = datetime.combine(item.appointment_date, item.end_time) - datetime.combine(item.appointment_date, item.start_time)
            self.assertEqual(duration, timedelta(minutes=item.service.duration_minutes))
            if item.status != AppointmentStatus.CANCELLED:
                slots[item.employee_id, item.appointment_date].append(item)
        for key, items in slots.items():
            ordered = sorted(items, key=lambda item: item.start_time)
            for previous, following in zip(ordered, ordered[1:]):
                with self.subTest(employee_date=key, appointments=(previous.pk, following.pk)):
                    self.assertLessEqual(previous.end_time, following.start_time)

    def test_default_demo_uses_english_names_and_euro_prices(self):
        self._setup_demo()
        self.assertTrue(Client.objects.filter(full_name='Emily Carter').exists())
        self.assertEqual(User.objects.get(username='demo_emma').get_full_name(), 'Emma Wilson')
        self.assertEqual(set(Service.objects.values_list('currency', flat=True)), {'EUR'})
        haircut = Service.objects.get(name="Women's haircut")
        self.assertEqual(haircut.price, 55)

    def test_currency_option_creates_independent_dollar_price_list(self):
        self._setup_demo(currency='USD')
        self.assertEqual(set(Service.objects.values_list('currency', flat=True)), {'USD'})
        self.assertEqual(Service.objects.get(name="Women's haircut").price, 60)
        before = self._snapshot()
        self._setup_demo(currency='EUR')
        self.assertEqual(self._snapshot(), before)

    def test_rerun_preserves_existing_rows_edits_and_passwords(self):
        self._setup_demo()
        edited_client = Client.objects.first()
        edited_client.full_name = 'Edited demo client'
        edited_client.save()
        admin = User.objects.get(username='demo_admin')
        admin.set_password('ChangedDemoPass2026!')
        admin.save()
        before = self._snapshot()

        output = self._setup_demo(password='DifferentDemoPass2026!')

        self.assertEqual(self._snapshot(), before)
        self.assertNotIn('Password:', output)
        admin.refresh_from_db()
        self.assertTrue(admin.check_password('ChangedDemoPass2026!'))

    def test_reset_refreshes_dates_credentials_and_data_only_inside_demo_workspace(self):
        other = self._other_workspace()
        other_org = other[0]
        other_rows = {
            model: list(model.objects.filter(organization=other_org).order_by('pk').values())
            for model in (User, Client, ServiceCategory, Service, Appointment, AuditLog)
        }
        with patch('users.management.commands.setup_demo.timezone.localdate', return_value=date(2026, 6, 1)):
            self._setup_demo()
        old_demo_ids = set(Appointment.objects.filter(organization__is_demo=True).values_list('pk', flat=True))

        with patch('users.management.commands.setup_demo.timezone.localdate', return_value=date(2026, 10, 1)):
            self._setup_demo(reset=True, password='RefreshedDemoPass2026!')

        org = Organization.objects.get(slug='orvanta-demo')
        self.assertEqual(Appointment.objects.filter(organization=org).count(), 180)
        self.assertTrue(Appointment.objects.filter(organization=org, appointment_date=date(2026, 10, 1)).exists())
        self.assertFalse(Appointment.objects.filter(organization=org, pk__in=old_demo_ids).exists())
        self.assertTrue(User.objects.get(username='demo_admin').check_password('RefreshedDemoPass2026!'))
        other_org.refresh_from_db()
        self.assertFalse(other_org.is_demo)
        for model, before in other_rows.items():
            self.assertEqual(list(model.objects.filter(organization=other_org).order_by('pk').values()), before)

    def test_existing_non_demo_organization_at_reserved_slug_is_never_modified(self):
        Organization.objects.create(name='Existing Business', slug='orvanta-demo')
        before = self._snapshot()

        for reset in (False, True):
            with self.subTest(reset=reset):
                with self.assertRaises(CommandError):
                    self._setup_demo(reset=reset)
                self.assertEqual(self._snapshot(), before)

    def test_reserved_username_in_another_organization_aborts_without_partial_demo(self):
        other_org = Organization.objects.create(name='Other Org', slug='other-org')
        owner = User.objects.create_user(username='demo_emma', organization=other_org)
        before = self._snapshot()

        with self.assertRaises(CommandError):
            self._setup_demo()

        self.assertEqual(self._snapshot(), before)
        owner.refresh_from_db()
        self.assertEqual(owner.organization, other_org)

    def test_existing_reserved_organization_name_does_not_create_partial_demo(self):
        Organization.objects.create(name='Orvanta Demo', slug='some-existing-business')
        before = self._snapshot()

        with self.assertRaises(CommandError):
            self._setup_demo()

        self.assertEqual(self._snapshot(), before)

    def test_invalid_password_is_rejected_before_any_data_is_created(self):
        before = self._snapshot()

        with self.assertRaises(CommandError):
            self._setup_demo(password='short')

        self.assertEqual(self._snapshot(), before)

    def test_invalid_password_on_reset_leaves_existing_demo_unchanged(self):
        self._setup_demo()
        before = self._snapshot()

        with self.assertRaises(CommandError):
            self._setup_demo(reset=True, password='short')

        self.assertEqual(self._snapshot(), before)

    def test_reset_refuses_foreign_appointments_referencing_demo_entities(self):
        self._setup_demo()
        other_org, owner, employee, client, service, _ = self._other_workspace()
        demo_client = Client.objects.filter(organization__is_demo=True).first()
        demo_service = Service.objects.filter(organization__is_demo=True).first()
        demo_employee = User.objects.get(username='demo_emma')
        demo_admin = User.objects.get(username='demo_admin')

        for overrides in (
            {'client': demo_client}, {'service': demo_service},
            {'employee': demo_employee}, {'created_by': demo_admin},
        ):
            with self.subTest(reference=tuple(overrides)):
                data = dict(
                    client=client, service=service, employee=employee, created_by=owner,
                    organization=other_org, appointment_date=date(2026, 6, 20),
                    start_time='09:00', end_time='10:00',
                )
                data.update(overrides)
                foreign = Appointment.objects.create(**data)
                before = self._snapshot()
                with self.assertRaises(CommandError):
                    self._setup_demo(reset=True)
                self.assertEqual(self._snapshot(), before)
                foreign.delete()

    def test_reset_refuses_foreign_client_created_by_demo_user(self):
        self._setup_demo()
        other_org = Organization.objects.create(name='Other Org', slug='other-org')
        Client.objects.create(
            full_name='Foreign Client', phone='+380501000002', organization=other_org,
            created_by=User.objects.get(username='demo_admin'),
        )
        before = self._snapshot()

        with self.assertRaises(CommandError):
            self._setup_demo(reset=True)

        self.assertEqual(self._snapshot(), before)

    def test_generated_password_is_printed_once_and_can_authenticate_demo_users(self):
        output = StringIO()
        call_command('setup_demo', stdout=output)
        match = re.search(r'^Password: (\S+)\s*$', output.getvalue(), re.MULTILINE)

        self.assertIsNotNone(match, output.getvalue())
        password = match.group(1)
        self.assertNotEqual(password, self.password)
        self.assertTrue(User.objects.get(username='demo_admin').check_password(password))
        self.assertTrue(User.objects.get(username='demo_emma').check_password(password))
        self.assertNotIn(password, self._setup_demo())

    def test_population_failure_rolls_back_new_setup_and_destructive_reset(self):
        def fail_after_writing(command, organization, password, today, currency):
            Client.objects.create(
                full_name='Partially written client', phone='+380501000003',
                organization=organization,
            )
            raise RuntimeError('Population failed')

        for reset in (False, True):
            with self.subTest(reset=reset):
                if reset:
                    self._setup_demo()
                before = self._snapshot()
                with patch(
                    'users.management.commands.setup_demo.Command._populate',
                    autospec=True, side_effect=fail_after_writing,
                ):
                    with self.assertRaisesMessage(RuntimeError, 'Population failed'):
                        self._setup_demo(reset=reset)
                self.assertEqual(self._snapshot(), before)
