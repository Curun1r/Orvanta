from datetime import date, time, timedelta
from decimal import Decimal

from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse

from clients.models import Client
from services_catalog.models import Service, ServiceCategory
from users.models import Organization, User, UserRole

from .forms import AppointmentForm
from .models import Appointment, AppointmentStatus, AppointmentStatusHistory
from .scheduling import APPOINTMENT_CONFLICT_MESSAGE


class AppointmentFormConflictValidationTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name='Org One', slug='org-one')
        self.other_organization = Organization.objects.create(name='Org Two', slug='org-two')

        self.manager = User.objects.create_user(
            username='manager_user',
            email='manager@example.com',
            password='StrongPass123!',
            role=UserRole.MANAGER,
            organization=self.organization,
        )
        self.employee = User.objects.create_user(
            username='employee_one',
            email='employee_one@example.com',
            password='StrongPass123!',
            role=UserRole.EMPLOYEE,
            organization=self.organization,
            is_active=True,
        )
        self.employee_two = User.objects.create_user(
            username='employee_two',
            email='employee_two@example.com',
            password='StrongPass123!',
            role=UserRole.EMPLOYEE,
            organization=self.organization,
            is_active=True,
        )
        self.other_employee = User.objects.create_user(
            username='employee_other_org',
            email='employee_other@example.com',
            password='StrongPass123!',
            role=UserRole.EMPLOYEE,
            organization=self.other_organization,
            is_active=True,
        )

        self.client = Client.objects.create(
            full_name='Client One',
            phone='+380500000001',
            organization=self.organization,
            created_by=self.manager,
        )
        self.other_client = Client.objects.create(
            full_name='Client Two',
            phone='+380500000002',
            organization=self.other_organization,
            created_by=self.other_employee,
        )

        self.category = ServiceCategory.objects.create(
            name='Category One',
            organization=self.organization,
        )
        self.other_category = ServiceCategory.objects.create(
            name='Category Two',
            organization=self.other_organization,
        )

        self.service = Service.objects.create(
            category=self.category,
            name='Service One',
            price='1000.00',
            duration_minutes=60,
            organization=self.organization,
        )
        self.other_service = Service.objects.create(
            category=self.other_category,
            name='Service Two',
            price='2000.00',
            duration_minutes=60,
            organization=self.other_organization,
        )

    def _create_appointment(
        self,
        *,
        organization,
        client,
        service,
        employee,
        appointment_date='2026-05-10',
        start_time='10:00',
        end_time='11:00',
        status=AppointmentStatus.PLANNED,
        actual_price=None,
    ):
        return Appointment.objects.create(
            client=client,
            service=service,
            employee=employee,
            created_by=self.manager,
            organization=organization,
            appointment_date=appointment_date,
            start_time=start_time,
            end_time=end_time,
            status=status,
            actual_price=actual_price,
        )

    def _form_data(
        self,
        *,
        client=None,
        service=None,
        employee=None,
        appointment_date='2026-05-10',
        start_time='10:00',
        end_time='11:00',
        status=AppointmentStatus.PLANNED,
        actual_price=None,
    ):
        data = {
            'client': (client or self.client).pk,
            'service': (service or self.service).pk,
            'employee': (employee or self.employee).pk,
            'appointment_date': appointment_date,
            'start_time': start_time,
            'end_time': end_time,
            'status': status,
            'comment': '',
        }
        if actual_price is not None:
            data['actual_price'] = actual_price
        return data

    def test_can_create_appointment_when_time_does_not_overlap(self):
        self._create_appointment(
            organization=self.organization,
            client=self.client,
            service=self.service,
            employee=self.employee,
            start_time='10:00',
            end_time='11:00',
        )

        form = AppointmentForm(
            data=self._form_data(start_time='11:00', end_time='12:00'),
            organization=self.organization,
        )

        self.assertTrue(form.is_valid(), form.errors)

    def test_cannot_create_appointment_when_time_overlaps_for_same_employee(self):
        self._create_appointment(
            organization=self.organization,
            client=self.client,
            service=self.service,
            employee=self.employee,
            start_time='10:00',
            end_time='11:00',
        )

        form = AppointmentForm(
            data=self._form_data(start_time='10:30', end_time='11:30'),
            organization=self.organization,
        )

        self.assertFalse(form.is_valid())
        self.assertIn(
            'У цього співробітника вже є запис на обраний проміжок часу.',
            form.non_field_errors(),
        )

    def test_cancelled_appointment_does_not_block_new_one(self):
        self._create_appointment(
            organization=self.organization,
            client=self.client,
            service=self.service,
            employee=self.employee,
            start_time='10:00',
            end_time='11:00',
            status=AppointmentStatus.CANCELLED,
        )

        form = AppointmentForm(
            data=self._form_data(start_time='10:30', end_time='10:45'),
            organization=self.organization,
        )

        self.assertTrue(form.is_valid(), form.errors)

    def test_can_create_same_time_for_other_employee(self):
        self._create_appointment(
            organization=self.organization,
            client=self.client,
            service=self.service,
            employee=self.employee,
        )

        form = AppointmentForm(
            data=self._form_data(employee=self.employee_two),
            organization=self.organization,
        )

        self.assertTrue(form.is_valid(), form.errors)

    def test_can_create_same_time_in_other_organization(self):
        self._create_appointment(
            organization=self.organization,
            client=self.client,
            service=self.service,
            employee=self.employee,
        )

        form = AppointmentForm(
            data=self._form_data(
                client=self.other_client,
                service=self.other_service,
                employee=self.other_employee,
            ),
            organization=self.other_organization,
        )

        self.assertTrue(form.is_valid(), form.errors)

    def test_update_does_not_conflict_with_itself(self):
        appointment = self._create_appointment(
            organization=self.organization,
            client=self.client,
            service=self.service,
            employee=self.employee,
            start_time='09:00',
            end_time='10:00',
        )

        form = AppointmentForm(
            data=self._form_data(start_time='09:00', end_time='10:00'),
            instance=appointment,
            organization=self.organization,
        )

        self.assertTrue(form.is_valid(), form.errors)

    def test_update_fails_when_time_overlaps_other_appointment(self):
        self._create_appointment(
            organization=self.organization,
            client=self.client,
            service=self.service,
            employee=self.employee,
            start_time='09:00',
            end_time='10:00',
        )
        editable_appointment = self._create_appointment(
            organization=self.organization,
            client=self.client,
            service=self.service,
            employee=self.employee,
            start_time='10:00',
            end_time='11:00',
        )

        form = AppointmentForm(
            data=self._form_data(start_time='09:30', end_time='10:30'),
            instance=editable_appointment,
            organization=self.organization,
        )

        self.assertFalse(form.is_valid())
        self.assertIn(
            'У цього співробітника вже є запис на обраний проміжок часу.',
            form.non_field_errors(),
        )

    def test_start_time_must_be_earlier_than_end_time(self):
        form = AppointmentForm(
            data=self._form_data(start_time='12:00', end_time='12:00'),
            organization=self.organization,
        )

        self.assertFalse(form.is_valid())
        self.assertIn(
            'Час завершення запису повинен бути пізнішим за час початку.',
            form.non_field_errors(),
        )

    def test_actual_price_can_be_saved_when_creating_appointment(self):
        form = AppointmentForm(
            data=self._form_data(actual_price='1250.50'),
            organization=self.organization,
        )

        self.assertTrue(form.is_valid(), form.errors)
        appointment = form.save(commit=False)
        appointment.organization = self.organization
        appointment.created_by = self.manager
        appointment.save()

        self.assertEqual(appointment.actual_price, Decimal('1250.50'))

    def test_actual_price_can_be_updated_on_existing_appointment(self):
        appointment = self._create_appointment(
            organization=self.organization,
            client=self.client,
            service=self.service,
            employee=self.employee,
            actual_price=Decimal('1000.00'),
        )

        form = AppointmentForm(
            data=self._form_data(actual_price='1350.00'),
            instance=appointment,
            organization=self.organization,
        )

        self.assertTrue(form.is_valid(), form.errors)
        updated_appointment = form.save()
        self.assertEqual(updated_appointment.actual_price, Decimal('1350.00'))

    def test_negative_actual_price_is_invalid(self):
        form = AppointmentForm(
            data=self._form_data(actual_price='-1.00'),
            organization=self.organization,
        )

        self.assertFalse(form.is_valid())
        self.assertIn('actual_price', form.errors)


class AppointmentListPaginationTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name='Appointment Org', slug='appointment-org')
        self.other_organization = Organization.objects.create(
            name='Other Appointment Org',
            slug='other-appointment-org',
        )

        self.manager = User.objects.create_user(
            username='appointment_manager',
            email='appointment_manager@example.com',
            password='StrongPass123!',
            role=UserRole.MANAGER,
            organization=self.organization,
        )
        self.employee = User.objects.create_user(
            username='appointment_employee',
            email='appointment_employee@example.com',
            password='StrongPass123!',
            role=UserRole.EMPLOYEE,
            organization=self.organization,
        )
        self.other_employee = User.objects.create_user(
            username='appointment_other_employee',
            email='appointment_other_employee@example.com',
            password='StrongPass123!',
            role=UserRole.EMPLOYEE,
            organization=self.organization,
        )
        self.external_employee = User.objects.create_user(
            username='appointment_external_employee',
            email='appointment_external_employee@example.com',
            password='StrongPass123!',
            role=UserRole.EMPLOYEE,
            organization=self.other_organization,
        )

        self.client_record = Client.objects.create(
            full_name='Appointment Client',
            phone='+380507000001',
            organization=self.organization,
            created_by=self.manager,
        )
        self.external_client_record = Client.objects.create(
            full_name='External Appointment Client',
            phone='+380507000002',
            organization=self.other_organization,
            created_by=self.external_employee,
        )
        self.category = ServiceCategory.objects.create(
            name='Appointment Category',
            organization=self.organization,
        )
        self.external_category = ServiceCategory.objects.create(
            name='External Appointment Category',
            organization=self.other_organization,
        )
        self.service = Service.objects.create(
            category=self.category,
            name='Appointment Service',
            price='100.00',
            duration_minutes=60,
            organization=self.organization,
        )
        self.external_service = Service.objects.create(
            category=self.external_category,
            name='External Appointment Service',
            price='100.00',
            duration_minutes=60,
            organization=self.other_organization,
        )

    def _create_appointments(self, count, *, employee, organization=None, start_index=0):
        organization = organization or self.organization
        client = self.client_record
        service = self.service
        created_by = self.manager

        if organization != self.organization:
            client = self.external_client_record
            service = self.external_service
            created_by = self.external_employee

        for index in range(count):
            Appointment.objects.create(
                client=client,
                service=service,
                employee=employee,
                created_by=created_by,
                appointment_date=date(2026, 5, 1) + timedelta(days=start_index + index),
                start_time=time(9, 0),
                end_time=time(10, 0),
                status=AppointmentStatus.PLANNED,
                organization=organization,
            )

    def _create_appointment(
        self,
        *,
        employee=None,
        organization=None,
        appointment_date=date(2026, 5, 10),
        start_time=time(9, 0),
        end_time=time(10, 0),
        status=AppointmentStatus.PLANNED,
        comment='',
        actual_price=None,
    ):
        organization = organization or self.organization
        client = self.client_record
        service = self.service
        created_by = self.manager

        if organization != self.organization:
            client = self.external_client_record
            service = self.external_service
            created_by = self.external_employee

        return Appointment.objects.create(
            client=client,
            service=service,
            employee=employee or self.employee,
            created_by=created_by,
            appointment_date=appointment_date,
            start_time=start_time,
            end_time=end_time,
            status=status,
            comment=comment,
            actual_price=actual_price,
            organization=organization,
        )

    def _csv_text(self, response):
        return response.content.decode('utf-8-sig')

    def test_employee_appointment_list_is_paginated_and_limited_to_own_records(self):
        self._create_appointments(12, employee=self.employee)
        self._create_appointments(12, employee=self.other_employee, start_index=30)
        self._create_appointments(
            5,
            employee=self.external_employee,
            organization=self.other_organization,
            start_index=60,
        )
        self.client.force_login(self.employee)

        first_page = self.client.get(reverse('appointment_list'))
        second_page = self.client.get(reverse('appointment_list'), {'page': '2'})

        self.assertEqual(first_page.status_code, 200)
        self.assertEqual(first_page.context['page_obj'].paginator.count, 12)
        self.assertEqual(len(first_page.context['page_obj']), 10)
        self.assertEqual(len(second_page.context['page_obj']), 2)
        self.assertTrue(
            all(appointment.employee == self.employee for appointment in first_page.context['page_obj'])
        )
        self.assertTrue(
            all(appointment.employee == self.employee for appointment in second_page.context['page_obj'])
        )

    def test_manager_exports_appointments_for_current_organization_only(self):
        self._create_appointment(comment='Organization appointment')
        self._create_appointment(
            employee=self.external_employee,
            organization=self.other_organization,
            comment='External organization appointment',
        )
        self.client.force_login(self.manager)

        response = self.client.get(reverse('appointment_export_csv'))
        csv_text = self._csv_text(response)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv; charset=utf-8')
        self.assertTrue(
            response['Content-Disposition'].startswith(
                'attachment; filename="appointments_export_',
            )
        )
        self.assertIn(
            'ID;Клієнт;Послуга;Базова вартість послуги;Фактична вартість запису;'
            'Співробітник;Дата;Час початку;Час завершення',
            csv_text,
        )
        self.assertIn('Organization appointment', csv_text)
        self.assertIn('Appointment Client', csv_text)
        self.assertNotIn('External organization appointment', csv_text)
        self.assertNotIn('External Appointment Client', csv_text)

    def test_employee_exports_only_own_appointments(self):
        self._create_appointment(employee=self.employee, comment='Own employee appointment')
        self._create_appointment(
            employee=self.other_employee,
            start_time=time(11, 0),
            end_time=time(12, 0),
            comment='Other employee appointment',
        )
        self._create_appointment(
            employee=self.external_employee,
            organization=self.other_organization,
            start_time=time(13, 0),
            end_time=time(14, 0),
            comment='External employee appointment',
        )
        self.client.force_login(self.employee)

        response = self.client.get(reverse('appointment_export_csv'))
        csv_text = self._csv_text(response)

        self.assertEqual(response.status_code, 200)
        self.assertIn('Own employee appointment', csv_text)
        self.assertNotIn('Other employee appointment', csv_text)
        self.assertNotIn('External employee appointment', csv_text)

    def test_appointment_export_respects_status_filter(self):
        self._create_appointment(
            status=AppointmentStatus.CANCELLED,
            comment='Cancelled export appointment',
        )
        self._create_appointment(
            status=AppointmentStatus.COMPLETED,
            start_time=time(11, 0),
            end_time=time(12, 0),
            comment='Completed export appointment',
        )
        self.client.force_login(self.manager)

        response = self.client.get(
            reverse('appointment_export_csv'),
            {'status': AppointmentStatus.CANCELLED},
        )
        csv_text = self._csv_text(response)

        self.assertEqual(response.status_code, 200)
        self.assertIn('Скасовано', csv_text)
        self.assertIn('Cancelled export appointment', csv_text)
        self.assertNotIn('Completed export appointment', csv_text)

    def test_appointment_export_respects_appointment_date_filter(self):
        self._create_appointment(
            appointment_date=date(2026, 5, 10),
            comment='Selected date appointment',
        )
        self._create_appointment(
            appointment_date=date(2026, 5, 11),
            comment='Other date appointment',
        )
        self.client.force_login(self.manager)

        response = self.client.get(
            reverse('appointment_export_csv'),
            {'appointment_date': '2026-05-10'},
        )
        csv_text = self._csv_text(response)

        self.assertEqual(response.status_code, 200)
        self.assertIn('Selected date appointment', csv_text)
        self.assertIn('2026-05-10', csv_text)
        self.assertNotIn('Other date appointment', csv_text)

    def test_appointment_export_includes_base_and_actual_prices(self):
        self._create_appointment(
            status=AppointmentStatus.COMPLETED,
            comment='Paid export appointment',
            actual_price=Decimal('175.25'),
        )
        self.client.force_login(self.manager)

        response = self.client.get(reverse('appointment_export_csv'))
        csv_text = self._csv_text(response)

        self.assertEqual(response.status_code, 200)
        self.assertIn('Базова вартість послуги', csv_text)
        self.assertIn('Фактична вартість запису', csv_text)
        self.assertIn('100.00', csv_text)
        self.assertIn('175.25', csv_text)
        self.assertIn('Paid export appointment', csv_text)

    def test_quick_completed_status_does_not_require_actual_price(self):
        appointment = self._create_appointment(status=AppointmentStatus.PLANNED)
        self.client.force_login(self.employee)

        response = self.client.post(
            reverse(
                'appointment_quick_status_update',
                args=[appointment.pk, AppointmentStatus.COMPLETED],
            ),
        )

        appointment.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(appointment.status, AppointmentStatus.COMPLETED)
        self.assertIsNone(appointment.actual_price)

    def test_cancelled_appointment_cannot_be_reactivated_into_an_occupied_slot(self):
        self._create_appointment(start_time=time(9, 30), end_time=time(10, 30))
        cancelled = self._create_appointment(status=AppointmentStatus.CANCELLED)
        self.client.force_login(self.employee)

        for status in (AppointmentStatus.CONFIRMED, AppointmentStatus.COMPLETED):
            with self.subTest(status=status):
                response = self.client.post(reverse(
                    'appointment_quick_status_update', args=[cancelled.pk, status],
                ))

                cancelled.refresh_from_db()
                self.assertRedirects(response, reverse('appointment_list'))
                self.assertEqual(cancelled.status, AppointmentStatus.CANCELLED)
                self.assertFalse(cancelled.status_history.exists())
                self.assertIn(
                    APPOINTMENT_CONFLICT_MESSAGE,
                    [str(message) for message in get_messages(response.wsgi_request)],
                )

    def test_cancelled_appointment_can_be_reactivated_in_a_free_slot(self):
        self.client.force_login(self.manager)
        for status in (AppointmentStatus.CONFIRMED, AppointmentStatus.COMPLETED):
            with self.subTest(status=status):
                cancelled = self._create_appointment(status=AppointmentStatus.CANCELLED)
                response = self.client.post(reverse(
                    'appointment_quick_status_update', args=[cancelled.pk, status],
                ))

                cancelled.refresh_from_db()
                self.assertRedirects(response, reverse('appointment_list'))
                self.assertEqual(cancelled.status, status)
                history = cancelled.status_history.get()
                self.assertEqual(history.old_status, AppointmentStatus.CANCELLED)
                self.assertEqual(history.new_status, status)
                self.assertEqual(history.changed_by, self.manager)
                cancelled.delete()

    def test_adjacent_appointment_does_not_block_reactivation(self):
        self._create_appointment(start_time=time(10), end_time=time(11))
        cancelled = self._create_appointment(status=AppointmentStatus.CANCELLED)
        self.client.force_login(self.employee)

        self.client.post(reverse(
            'appointment_quick_status_update',
            args=[cancelled.pk, AppointmentStatus.CONFIRMED],
        ))

        cancelled.refresh_from_db()
        self.assertEqual(cancelled.status, AppointmentStatus.CONFIRMED)

    def test_other_employee_or_date_does_not_block_reactivation(self):
        self._create_appointment(employee=self.other_employee)
        self._create_appointment(appointment_date=date(2026, 5, 11))
        cancelled = self._create_appointment(status=AppointmentStatus.CANCELLED)
        self.client.force_login(self.manager)

        self.client.post(reverse(
            'appointment_quick_status_update',
            args=[cancelled.pk, AppointmentStatus.CONFIRMED],
        ))

        cancelled.refresh_from_db()
        self.assertEqual(cancelled.status, AppointmentStatus.CONFIRMED)

    def test_cancellation_releases_slot_and_an_unchanged_status_creates_no_history(self):
        appointment = self._create_appointment()
        self.client.force_login(self.employee)
        status_url = reverse(
            'appointment_quick_status_update',
            args=[appointment.pk, AppointmentStatus.CANCELLED],
        )

        self.client.post(status_url)
        self.client.post(status_url)

        appointment.refresh_from_db()
        self.assertEqual(appointment.status, AppointmentStatus.CANCELLED)
        self.assertEqual(appointment.status_history.count(), 1)
        form = AppointmentForm(data={
            'client': self.client_record.pk, 'service': self.service.pk,
            'employee': self.employee.pk, 'appointment_date': '2026-05-10',
            'start_time': '09:00', 'end_time': '10:00',
            'status': AppointmentStatus.PLANNED,
        }, organization=self.organization)
        self.assertTrue(form.is_valid(), form.errors)

    def test_employee_cannot_read_or_change_colleague_appointment_directly(self):
        appointment = self._create_appointment(employee=self.other_employee)
        self.client.force_login(self.employee)

        detail = self.client.get(reverse('appointment_detail', args=[appointment.pk]))
        update = self.client.post(reverse(
            'appointment_quick_status_update',
            args=[appointment.pk, AppointmentStatus.COMPLETED],
        ))

        self.assertEqual(detail.status_code, 404)
        self.assertEqual(update.status_code, 404)
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, AppointmentStatus.PLANNED)
        self.assertFalse(appointment.status_history.exists())

    def test_manager_can_read_colleague_appointment_but_not_another_organization(self):
        appointment = self._create_appointment(employee=self.other_employee)
        external = self._create_appointment(
            employee=self.external_employee, organization=self.other_organization,
        )
        self.client.force_login(self.manager)

        self.assertEqual(self.client.get(reverse(
            'appointment_detail', args=[appointment.pk],
        )).status_code, 200)
        self.assertEqual(self.client.get(reverse(
            'appointment_detail', args=[external.pk],
        )).status_code, 404)
        self.assertEqual(self.client.post(reverse(
            'appointment_quick_status_update',
            args=[external.pk, AppointmentStatus.COMPLETED],
        )).status_code, 404)

    def test_create_and_edit_reject_overlapping_slots_through_http(self):
        self._create_appointment()
        editable = self._create_appointment(start_time=time(11), end_time=time(12))
        self.client.force_login(self.manager)
        data = {
            'client': self.client_record.pk, 'service': self.service.pk,
            'employee': self.employee.pk, 'appointment_date': '2026-05-10',
            'start_time': '09:30', 'end_time': '10:30',
            'status': AppointmentStatus.PLANNED,
        }

        for url in (
            reverse('appointment_create'),
            reverse('appointment_update', args=[editable.pk]),
        ):
            with self.subTest(url=url):
                response = self.client.post(url, data)
                self.assertEqual(response.status_code, 200)
                self.assertIn(
                    APPOINTMENT_CONFLICT_MESSAGE,
                    response.context['form'].non_field_errors(),
                )

        editable.refresh_from_db()
        self.assertEqual(editable.start_time, time(11))
        self.assertEqual(Appointment.objects.count(), 2)
        self.assertFalse(AppointmentStatusHistory.objects.exists())

    def test_manager_can_update_actual_price_from_appointment_list(self):
        appointment = self._create_appointment(actual_price=None)
        self.client.force_login(self.manager)
        next_url = f"{reverse('appointment_list')}?status={AppointmentStatus.PLANNED}&page=2"

        response = self.client.post(
            reverse('appointment_actual_price_update', args=[appointment.pk]),
            {
                'actual_price': '185.50',
                'next': next_url,
            },
        )

        appointment.refresh_from_db()
        self.assertRedirects(response, next_url, fetch_redirect_response=False)
        self.assertEqual(appointment.actual_price, Decimal('185.50'))

    def test_manager_can_clear_actual_price_from_appointment_list(self):
        appointment = self._create_appointment(actual_price=Decimal('185.50'))
        self.client.force_login(self.manager)

        response = self.client.post(
            reverse('appointment_actual_price_update', args=[appointment.pk]),
            {'actual_price': ''},
        )

        appointment.refresh_from_db()
        self.assertRedirects(response, reverse('appointment_list'))
        self.assertIsNone(appointment.actual_price)

    def test_negative_inline_actual_price_is_not_saved(self):
        appointment = self._create_appointment(actual_price=Decimal('185.50'))
        self.client.force_login(self.manager)

        response = self.client.post(
            reverse('appointment_actual_price_update', args=[appointment.pk]),
            {'actual_price': '-1.00'},
        )

        appointment.refresh_from_db()
        self.assertRedirects(response, reverse('appointment_list'))
        self.assertEqual(appointment.actual_price, Decimal('185.50'))

    def test_employee_cannot_update_actual_price_from_direct_post(self):
        appointment = self._create_appointment(
            employee=self.employee,
            actual_price=Decimal('185.50'),
        )
        self.client.force_login(self.employee)

        response = self.client.post(
            reverse('appointment_actual_price_update', args=[appointment.pk]),
            {'actual_price': '300.00'},
        )

        appointment.refresh_from_db()
        self.assertRedirects(response, reverse('home'))
        self.assertEqual(appointment.actual_price, Decimal('185.50'))
