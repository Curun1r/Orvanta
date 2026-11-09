from concurrent.futures import ThreadPoolExecutor
from datetime import date, time
from threading import Barrier
from unittest import skipUnless

from django.db import connection, connections
from django.test import Client as HttpClient, TransactionTestCase
from django.urls import reverse

from clients.models import Client
from services_catalog.models import Service, ServiceCategory
from users.models import Organization, User, UserRole

from .models import Appointment, AppointmentStatus, AppointmentStatusHistory


@skipUnless(connection.vendor == 'postgresql', 'Requires PostgreSQL row locking')
class ConcurrentAppointmentBookingTests(TransactionTestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name='Booking Org', slug='booking-org')
        self.manager = User.objects.create_user(
            username='booking_manager', role=UserRole.MANAGER,
            organization=self.organization,
        )
        self.employee = User.objects.create_user(
            username='booking_employee', role=UserRole.EMPLOYEE,
            organization=self.organization,
        )
        self.client_record = Client.objects.create(
            full_name='Booking Client', phone='+380501234567',
            organization=self.organization, created_by=self.manager,
        )
        category = ServiceCategory.objects.create(
            name='Booking Category', organization=self.organization,
        )
        self.service = Service.objects.create(
            name='Booking Service', category=category, price='100.00',
            duration_minutes=60, organization=self.organization,
        )
        self.data = {
            'client': self.client_record.pk, 'service': self.service.pk,
            'employee': self.employee.pk, 'appointment_date': '2026-05-10',
            'start_time': '10:00', 'end_time': '11:00',
            'status': AppointmentStatus.CONFIRMED,
        }

    def _concurrent_posts(self, requests):
        barrier = Barrier(len(requests))

        def post(request):
            try:
                client = HttpClient()
                client.force_login(User.objects.get(pk=self.manager.pk))
                barrier.wait(timeout=10)
                url, data = request
                return client.post(url, data).status_code
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=len(requests)) as pool:
            results = [pool.submit(post, request) for request in requests]
            return [result.result(timeout=20) for result in results]

    def _appointment(self, **overrides):
        data = dict(
            client=self.client_record, service=self.service, employee=self.employee,
            created_by=self.manager, organization=self.organization,
            appointment_date=date(2026, 5, 10), start_time=time(10), end_time=time(11),
        )
        data.update(overrides)
        return Appointment.objects.create(**data)

    def _active_slot_count(self):
        return Appointment.objects.filter(
            employee=self.employee, appointment_date=date(2026, 5, 10),
            start_time__lt=time(11), end_time__gt=time(10),
        ).exclude(status=AppointmentStatus.CANCELLED).count()

    def test_two_concurrent_creations_only_book_the_slot_once(self):
        create_url = reverse('appointment_create')
        statuses = self._concurrent_posts([
            (create_url, self.data), (create_url, self.data),
        ])

        self.assertEqual(sorted(statuses), [200, 302])
        self.assertEqual(self._active_slot_count(), 1)
        self.assertEqual(AppointmentStatusHistory.objects.count(), 1)

    def test_creation_and_reactivation_cannot_both_take_the_same_slot(self):
        cancelled = self._appointment(status=AppointmentStatus.CANCELLED)
        statuses = self._concurrent_posts([
            (reverse('appointment_create'), self.data),
            (reverse('appointment_quick_status_update', args=[
                cancelled.pk, AppointmentStatus.CONFIRMED,
            ]), {}),
        ])

        cancelled.refresh_from_db()
        self.assertEqual(statuses[1], 302)
        self.assertEqual(self._active_slot_count(), 1)
        self.assertEqual(AppointmentStatusHistory.objects.count(), 1)
        if statuses[0] == 302:
            self.assertEqual(cancelled.status, AppointmentStatus.CANCELLED)
        else:
            self.assertEqual(statuses[0], 200)
            self.assertEqual(cancelled.status, AppointmentStatus.CONFIRMED)

    def test_creation_and_rescheduling_cannot_both_take_the_same_slot(self):
        editable = self._appointment(start_time=time(8), end_time=time(9))
        statuses = self._concurrent_posts([
            (reverse('appointment_create'), self.data),
            (reverse('appointment_update', args=[editable.pk]), self.data),
        ])

        self.assertEqual(sorted(statuses), [200, 302])
        self.assertEqual(self._active_slot_count(), 1)
