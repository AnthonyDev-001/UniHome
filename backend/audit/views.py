from rest_framework import permissions, serializers, viewsets
from common.permissions import ReviewPermission
from common.views import RentalPagination
from .models import AuditEvent


class AuditSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditEvent
        fields = ['id', 'actor', 'action', 'target_type', 'target_id', 'reason', 'metadata', 'created_at']


class AuditViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AuditEvent.objects.all()
    serializer_class = AuditSerializer
    permission_classes = [permissions.IsAuthenticated, ReviewPermission]
    review_permission = 'audit.view_auditevent'
    pagination_class = RentalPagination
