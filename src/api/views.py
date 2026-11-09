from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ReadOnlyModelViewSet

from appointments.querysets import appointments_visible_to
from clients.models import Client
from config.views import get_dashboard_analytics
from services_catalog.models import Service

from .serializers import AppointmentSerializer, ClientSerializer, ServiceSerializer


class ClientViewSet(ReadOnlyModelViewSet):
    serializer_class = ClientSerializer


    def get_queryset(self):
        return Client.objects.filter(organization=self.request.user.organization)


class ServiceViewSet(ReadOnlyModelViewSet):
    serializer_class = ServiceSerializer


    def get_queryset(self):
        return Service.objects.select_related('category').filter(
            organization=self.request.user.organization,
        )


class AppointmentViewSet(ReadOnlyModelViewSet):
    serializer_class = AppointmentSerializer


    def get_queryset(self):
        return appointments_visible_to(self.request.user)


class DashboardAnalyticsApiView(APIView):


    def get(self, request):
        analytics = get_dashboard_analytics(request.user)
        analytics.pop('appointments_queryset', None)

        return Response(
            {
                'clients_count': analytics['clients_count'],
                'active_clients_count': analytics['active_clients_count'],
                'services_count': analytics['services_count'],
                'active_services_count': analytics['active_services_count'],
                'appointments_count': analytics['appointments_count'],
                'employees_count': analytics['employees_count'],
                'completed_count': analytics['completed_count'],
                'cancelled_count': analytics['cancelled_count'],
                'total_revenue': analytics['total_revenue'],
                'average_check': analytics['average_check'],
                'revenue_appointments_count': analytics['revenue_appointments_count'],
                'status_counts': [
                    {
                        'status': item['status'],
                        'total': item['total'],
                    }
                    for item in analytics['status_counts']
                ],
                'popular_services': [
                    {
                        'service_name': item['service__name'],
                        'total': item['total'],
                    }
                    for item in analytics['popular_services']
                ],
                'employee_workload': [
                    {
                        'employee_username': item['employee__username'],
                        'total': item['total'],
                    }
                    for item in analytics['employee_workload']
                ],
            }
        )
