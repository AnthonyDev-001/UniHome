from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from common.admin import ReadOnlyAdmin, ReviewAdmin
from common.permissions import can_review
from django.db.models import Q
from .models import EvidenceDocument, PropertyAuthority, VerificationCase
from .services import review


@admin.register(VerificationCase)
class VerificationAdmin(ReviewAdmin):
    review_permission = 'verification.review_verification'
    list_display = ['id', 'applicant', 'role', 'status', 'expires_at']
    list_filter = ['status', 'role']

    def review_object(self, actor, obj, decision, reason, expires_at, expected_revision=None):
        review(actor, obj, decision, reason, expires_at)


@admin.register(PropertyAuthority)
class AuthorityAdmin(VerificationAdmin):
    review_permission = 'verification.review_authority'
    list_display = ['id', 'property', 'representative', 'status', 'expires_at']
    list_filter = ['status']


@admin.register(EvidenceDocument)
class EvidenceAdmin(ReadOnlyAdmin):
    list_display = ['id', 'case', 'authority', 'content_type', 'size', 'created_at']
    exclude = ['file']

    def get_readonly_fields(self, request, obj=None):
        return [field for field in super().get_readonly_fields(request, obj) if field != 'file'] + ['download']

    def get_queryset(self, request):
        scope = Q(case__applicant=request.user) | Q(authority__representative=request.user)
        if can_review(request.user, 'verification.review_verification'):
            scope |= Q(case__isnull=False)
        if can_review(request.user, 'verification.review_authority'):
            scope |= Q(authority__isnull=False)
        return super().get_queryset(request).filter(scope)

    @admin.display(description='Authorized evidence download')
    def download(self, obj):
        return format_html('<a href="{}">Download as attachment</a>', reverse('evidence-document-file', args=[obj.pk]))
