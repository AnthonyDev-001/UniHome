from django.contrib import admin
from common.admin import ReadOnlyAdmin
from .models import AuditEvent


@admin.register(AuditEvent)
class AuditAdmin(ReadOnlyAdmin):
    list_display = ['created_at', 'actor', 'action', 'target_type', 'target_id']
    list_filter = ['action', 'target_type']
    search_fields = ['target_id']
