from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from common.admin import ListingActionForm, ReadOnlyAdmin, ReviewAdmin
from .models import (Amenity, AvailabilityBlock, ListingReport, ListingRevision, Property, PropertyMedia, Unit, UnitCharge)
from .services import review_listing, review_media, resolve_report


@admin.register(Property)
class PropertyAdmin(ReviewAdmin):
    action_form = ListingActionForm
    review_permission = 'properties.review_listing'
    list_display = ['title', 'category', 'city', 'status', 'revision', 'publisher']
    list_filter = ['status', 'category', 'city']
    search_fields = ['title', 'area', 'campus']

    def review_object(self, actor, obj, decision, reason, expires_at, expected_revision=None):
        review_listing(actor, obj, decision, reason, expected_revision)


@admin.register(PropertyMedia)
class MediaAdmin(ReviewAdmin):
    review_permission = 'properties.review_media'
    list_display = ['id', 'property', 'kind', 'status', 'size']
    list_filter = ['status', 'kind']
    exclude = ['file']
    actions = ['approve', 'reject']

    def get_readonly_fields(self, request, obj=None):
        return [field for field in super().get_readonly_fields(request, obj) if field != 'file'] + ['download']

    @admin.display(description='Authorized media review')
    def download(self, obj):
        return format_html('<a href="{}">Inspect file</a>', reverse('property-media-file', args=[obj.pk]))

    def review_object(self, actor, obj, decision, reason, expires_at, expected_revision=None):
        review_media(actor, obj, decision, reason)


@admin.register(Amenity)
class AmenityAdmin(ReadOnlyAdmin):
    def has_add_permission(self, request):
        return request.user.has_perm('properties.add_amenity')

    def get_readonly_fields(self, request, obj=None):
        return super().get_readonly_fields(request, obj) if obj else []


@admin.register(ListingReport)
class ReportAdmin(ReviewAdmin):
    review_permission = 'properties.review_listing'
    actions = ['resolve']

    @admin.action(description='Resolve selected reports')
    def resolve(self, request, queryset):
        self.decide(request, queryset, 'RESOLVED')

    def review_object(self, actor, obj, decision, reason, expires_at, expected_revision=None):
        resolve_report(actor, obj, reason)

    list_display = ['id', 'property', 'reason', 'resolved', 'created_at']
    list_filter = ['resolved', 'reason']


for model in [Unit, UnitCharge, AvailabilityBlock, ListingRevision]:
    admin.site.register(model, ReadOnlyAdmin)
