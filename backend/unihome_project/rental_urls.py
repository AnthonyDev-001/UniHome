from django.urls import include, path
from rest_framework.routers import DefaultRouter
from audit.views import AuditViewSet
from properties.views import (AmenityViewSet, ChargeViewSet, MediaViewSet, ReportViewSet, PropertyManagementViewSet, PublicPropertyViewSet, UnitViewSet)
from verification.views import AuthorityViewSet, EvidenceViewSet, VerificationViewSet

router = DefaultRouter()
router.register('properties', PublicPropertyViewSet, basename='public-property')
router.register('management/properties', PropertyManagementViewSet, basename='managed-property')
router.register('units', UnitViewSet, basename='unit')
router.register('charges', ChargeViewSet, basename='unit-charge')
router.register('media', MediaViewSet, basename='property-media')
router.register('amenities', AmenityViewSet, basename='amenity')
router.register('verification/cases', VerificationViewSet, basename='verification-case')
router.register('verification/authorities', AuthorityViewSet, basename='property-authority')
router.register('verification/documents', EvidenceViewSet, basename='evidence-document')
router.register('reports', ReportViewSet, basename='listing-report')
router.register('audit', AuditViewSet, basename='audit-event')
urlpatterns = [path('', include(router.urls))]
