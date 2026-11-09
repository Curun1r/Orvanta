import secrets
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from appointments.models import Appointment, AppointmentStatus, AppointmentStatusHistory
from audit.context import audit_context
from audit.models import AuditLog
from clients.models import Client
from services_catalog.models import Service, ServiceCategory
from users.demo_data import CATEGORIES_AND_SERVICES, CLIENT_NAMES
from users.models import Organization, User, UserRole


DEMO_SLUG = 'orvanta-demo'
DEMO_NAME = 'Orvanta Demo'
DEMO_USERS = (
    ('demo_admin', 'Адміністратор', 'Демо', UserRole.ADMIN),
    ('demo_manager', 'Менеджер', 'Демо', UserRole.MANAGER),
    ('demo_olena', 'Олена', 'Коваль', UserRole.EMPLOYEE),
    ('demo_natalia', 'Наталія', 'Мельник', UserRole.EMPLOYEE),
    ('demo_iryna', 'Ірина', 'Савченко', UserRole.EMPLOYEE),
    ('demo_tetyana', 'Тетяна', 'Петренко', UserRole.EMPLOYEE),
    ('demo_oksana', 'Оксана', 'Гончар', UserRole.EMPLOYEE),
)


class Command(BaseCommand):
    help = 'Create an isolated demo workspace; reruns preserve it unless --reset is supplied.'

    def add_arguments(self, parser):
        parser.add_argument('--password', help='Initial password shared by the demo accounts.')
        parser.add_argument(
            '--reset', action='store_true',
            help='Replace data and passwords only in the marked demo workspace.',
        )

    def handle(self, *args, **options):
        try:
            with transaction.atomic(), audit_context(request=None, user=None):
                organization = (
                    Organization.objects.select_for_update(no_key=True)
                    .filter(slug=DEMO_SLUG).first()
                )
                if organization is not None and not organization.is_demo:
                    raise CommandError('The reserved slug belongs to a non-demo organization. No data changed.')

                usernames = [item[0] for item in DEMO_USERS]
                collisions = User.objects.filter(username__in=usernames)
                if organization is not None:
                    collisions = collisions.exclude(organization=organization)
                if collisions.exists():
                    raise CommandError('A demo username already belongs to another workspace. No data changed.')

                if organization is not None and not options['reset']:
                    self.stdout.write('Demo already exists. Data and passwords are unchanged.')
                    self.stdout.write('Use setup_demo --reset to refresh the demo workspace.')
                    return

                password = options['password']
                if password is None:
                    password = secrets.token_urlsafe(18) + '!aA1'
                try:
                    validate_password(password, User(username='demo_admin', email='demo_admin@example.test'))
                except ValidationError as error:
                    raise CommandError(' '.join(error.messages)) from error

                if organization is None:
                    if Organization.objects.filter(name=DEMO_NAME).exists():
                        raise CommandError('The reserved demo name is already in use. No data changed.')
                    organization = Organization.objects.create(
                        slug=DEMO_SLUG, name=DEMO_NAME, is_demo=True,
                    )
                else:
                    self._check_external_references(organization)
                    self._clear_demo(organization)

                self._populate(organization, password, timezone.localdate())
        except IntegrityError as error:
            raise CommandError('Demo setup conflicted with existing data. No data changed; retry after checking the workspace.') from error

        self.stdout.write(self.style.SUCCESS('Demo workspace is ready.'))
        self.stdout.write(f'Organization: {DEMO_SLUG}')
        self.stdout.write('Accounts: ' + ', '.join(usernames))
        self.stdout.write(f'Password: {password}')
        self.stdout.write('35 clients, 30 services, 5 employees and 180 appointments.')
        self.stdout.write('This password is shared by the demo accounts only. Reruns do not change it.')

    def _check_external_references(self, organization):
        external_appointments = Appointment.objects.exclude(organization=organization).filter(
            Q(client__organization=organization) | Q(service__organization=organization)
            | Q(employee__organization=organization) | Q(created_by__organization=organization)
        )
        external_clients = Client.objects.exclude(organization=organization).filter(
            created_by__organization=organization,
        )
        external_services = Service.objects.exclude(organization=organization).filter(
            category__organization=organization,
        )
        external_history = AppointmentStatusHistory.objects.exclude(organization=organization).filter(
            Q(appointment__organization=organization) | Q(changed_by__organization=organization),
        )
        external_logs = AuditLog.objects.exclude(organization=organization).filter(
            user__organization=organization,
        )
        if any(queryset.exists() for queryset in (
            external_appointments, external_clients, external_services, external_history, external_logs,
        )):
            raise CommandError('Other workspaces reference demo data. Reset refused; no data changed.')

    def _clear_demo(self, organization):
        AppointmentStatusHistory.objects.filter(organization=organization).delete()
        Appointment.objects.filter(organization=organization).delete()
        Client.objects.filter(organization=organization).delete()
        Service.objects.filter(organization=organization).delete()
        ServiceCategory.objects.filter(organization=organization).delete()
        User.objects.filter(organization=organization).delete()
        AuditLog.objects.filter(organization=organization).delete()

    def _populate(self, organization, password, today):
        users = []
        for username, first_name, last_name, role in DEMO_USERS:
            users.append(User.objects.create_user(
                username=username, password=password, first_name=first_name, last_name=last_name,
                email=f'{username}@example.test', role=role, organization=organization,
                is_active=True, is_staff=False, is_superuser=False,
            ))
        admin, _manager, *employees = users

        services = []
        for category_name, items in CATEGORIES_AND_SERVICES.items():
            category = ServiceCategory.objects.create(name=category_name, organization=organization)
            for name, price, duration in items:
                services.append(Service.objects.create(
                    name=name, category=category, price=Decimal(price), duration_minutes=duration,
                    organization=organization,
                ))

        clients = []
        for index, name in enumerate(CLIENT_NAMES):
            clients.append(Client.objects.create(
                full_name=name, phone=f'+38099000{index:04d}',
                email=f'client{index + 1}@example.test', notes='Вигаданий клієнт для демонстрації.',
                organization=organization, created_by=admin,
            ))

        for index in range(180):
            employee = employees[index % len(employees)]
            service = services[(index * 7) % len(services)]
            if index < 135:
                day = today - timedelta(days=1 + 3 * (index // 5))
                status = (
                    AppointmentStatus.CANCELLED if index % 10 == 0 else
                    AppointmentStatus.CONFIRMED if index % 10 == 1 else
                    AppointmentStatus.COMPLETED
                )
                hour = 9 + 3 * ((index // 5) % 3)
            elif index < 140:
                day, hour = today, 10
                status = AppointmentStatus.CANCELLED if index == 139 else AppointmentStatus.COMPLETED
            else:
                day = today + timedelta(days=1 + (index - 140) // 5)
                hour = 9 + 3 * (((index - 140) // 5) % 3)
                status = AppointmentStatus.PLANNED if index % 2 else AppointmentStatus.CONFIRMED

            start = datetime.combine(day, time(hour))
            end = start + timedelta(minutes=service.duration_minutes)
            actual_price = None
            if status == AppointmentStatus.COMPLETED and index % 7:
                factor = (Decimal('0.9'), Decimal('1'), Decimal('1.1'))[index % 3]
                actual_price = (service.price * factor).quantize(Decimal('0.01'))
            appointment = Appointment.objects.create(
                organization=organization, client=clients[index % len(clients)], service=service,
                employee=employee, created_by=admin, appointment_date=day,
                start_time=start.time(), end_time=end.time(), status=status, actual_price=actual_price,
                comment=f'Демонстраційний запис #{index + 1:03d}.',
            )
            AppointmentStatusHistory.objects.create(
                appointment=appointment, organization=organization, old_status=AppointmentStatus.PLANNED,
                new_status=status, changed_by=admin, comment='Демонстраційна історія статусу.',
            )
