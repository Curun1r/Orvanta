from rest_framework import serializers

from appointments.models import Appointment
from clients.models import Client
from services_catalog.models import Service, ServiceCategory


class ClientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Client
        fields = [
            'id',
            'full_name',
            'phone',
            'email',
            'birth_date',
            'notes',
            'is_active',
            'created_at',
            'updated_at',
        ]


class ServiceCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceCategory
        fields = [
            'id',
            'name',
            'description',
        ]


class ServiceSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    currency = serializers.CharField(read_only=True)

    class Meta:
        model = Service
        fields = [
            'id',
            'name',
            'description',
            'price',
            'duration_minutes',
            'is_active',
            'category',
            'category_name',
            'created_at',
            'updated_at',
            'currency',
        ]


class AppointmentSerializer(serializers.ModelSerializer):
    client_full_name = serializers.CharField(source='client.full_name', read_only=True)
    service_name = serializers.CharField(source='service.name', read_only=True)
    employee_username = serializers.CharField(source='employee.username', read_only=True)
    currency = serializers.CharField(source='service.currency', read_only=True)

    class Meta:
        model = Appointment
        fields = [
            'id',
            'client',
            'client_full_name',
            'service',
            'service_name',
            'employee',
            'employee_username',
            'status',
            'appointment_date',
            'start_time',
            'end_time',
            'actual_price',
            'comment',
            'created_at',
            'updated_at',
            'currency',
        ]
