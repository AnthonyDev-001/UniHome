from datetime import timedelta
from django.db import transaction
from django.db.models import Exists, OuterRef, Q
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from rest_framework import mixins, permissions, serializers, viewsets
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication

from audit.models import record
from common.permissions import ReviewPermission, can_review
from common.serializers import ListingReviewInput, MediaReviewInput
from common.uploads import digest, normalize_image, validate_video
from common.views import ConflictResponseMixin, RentalPagination
from verification.services import lock_user
from .models import Amenity, AvailabilityBlock, ListingReport, Property, PropertyMedia, Unit, UnitCharge
from .serializers import (AmenitySerializer, AvailabilityInput, AvailabilitySerializer, ChargeSerializer,
                         MediaSerializer, PropertySerializer, PublicPropertySerializer, SearchInput, UnitSerializer)
from .services import (add_availability_block, changed, lock_property, managed_properties,
                       public_properties, review_listing, review_media, submit_listing)


class PublicPropertyViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [permissions.AllowAny]
    serializer_class = PublicPropertySerializer
    pagination_class = RentalPagination

    def get_queryset(self):
        rows = public_properties().prefetch_related('amenities', 'units__charges', 'media')
        if self.action != 'list':
            return rows
        search = SearchInput(data=self.request.query_params)
        search.is_valid(raise_exception=True)
        values = search.validated_data
        for field in ['category', 'city', 'area', 'campus']:
            if field in values:
                rows = rows.filter(**{field if field == 'category' else f'{field}__icontains': values[field]})
        unit_filters = {}
        for field in ['kind', 'billing_period']:
            if field in values:
                unit_filters[field] = values[field]
        for input_name, lookup in [('min_rent', 'rent__gte'), ('max_rent', 'rent__lte')]:
            if input_name in values:
                unit_filters[lookup] = values[input_name]
        if unit_filters or 'available_on' in values:
            units = Unit.objects.filter(property_id=OuterRef('pk'), **unit_filters)
            if 'available_on' in values:
                date = values['available_on']
                blocking = AvailabilityBlock.objects.filter(unit_id=OuterRef('pk'), cancelled=False, starts_on__lte=date, ends_on__gt=date)
                units = units.filter(status=Unit.Status.AVAILABLE, available_from__lte=date).annotate(blocked=Exists(blocking)).filter(blocked=False)
            rows = rows.annotate(matching_unit=Exists(units)).filter(matching_unit=True)
        return rows

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def report(self, request, pk=None):
        property = self.get_object()
        class ReportInput(serializers.Serializer):
            reason = serializers.ChoiceField(choices=ListingReport._meta.get_field('reason').choices)
            details = serializers.CharField(max_length=2000)
        data = ReportInput(data=request.data)
        data.is_valid(raise_exception=True)
        with transaction.atomic():
            obj = ListingReport.objects.create(property=property, reporter=request.user, **data.validated_data)
            record(request.user, 'listing.reported', obj, property_id=str(property.pk))
        return Response({'id': str(obj.pk), 'resolved': False}, status=201)


class PropertyManagementViewSet(ConflictResponseMixin, mixins.CreateModelMixin, mixins.UpdateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = PropertySerializer
    review_permission = 'properties.review_listing'

    def get_queryset(self):
        rows = Property.objects.all() if can_review(self.request.user, self.review_permission) else managed_properties(self.request.user)
        return rows.prefetch_related('units__charges', 'media', 'amenities')

    @transaction.atomic
    def perform_create(self, serializer):
        lock_user(self.request.user.pk)
        obj = serializer.save(created_by=self.request.user)
        record(self.request.user, 'property.created', obj)

    @transaction.atomic
    def perform_update(self, serializer):
        property = lock_property(self.request.user, serializer.instance.pk)
        serializer.instance = property
        obj = serializer.save()
        changed(self.request.user, obj, 'property.changed', fields=sorted(serializer.validated_data))

    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        return Response(self.get_serializer(submit_listing(request.user, self.get_object())).data)

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated, ReviewPermission])
    def review(self, request, pk=None):
        obj = self.get_object()
        data = ListingReviewInput(data=request.data)
        data.is_valid(raise_exception=True)
        values = dict(data.validated_data)
        values.pop('expires_at', None)
        return Response(self.get_serializer(review_listing(request.user, obj, **values)).data)

    @action(detail=True, methods=['post'])
    @transaction.atomic
    def withdraw(self, request, pk=None):
        obj = self.get_object()
        obj = lock_property(request.user, obj.pk)
        if request.data.get('status') not in {Property.Status.UNAVAILABLE, Property.Status.ARCHIVED}:
            raise ValidationError({'status': 'Use UNAVAILABLE or ARCHIVED.'})
        if obj.status == Property.Status.SUSPENDED and request.data['status'] != Property.Status.ARCHIVED:
            raise ValidationError('Only a reviewer can reopen a suspended listing.')
        obj.status = request.data['status']
        obj.save(update_fields=['status', 'updated_at'])
        record(request.user, 'listing.withdrawn', obj, status=obj.status)
        return Response(self.get_serializer(obj).data)

    @action(detail=True, methods=['get'])
    def revisions(self, request, pk=None):
        obj = self.get_object()
        return Response(list(obj.submissions.order_by('-number').values('number', 'sha256', 'created_at')))


class UnitViewSet(ConflictResponseMixin, mixins.CreateModelMixin, mixins.UpdateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = UnitSerializer

    def get_queryset(self):
        return Unit.objects.filter(property__in=managed_properties(self.request.user)).select_related('property').prefetch_related('charges')

    @transaction.atomic
    def perform_create(self, serializer):
        property = lock_property(self.request.user, serializer.validated_data['property'].pk)
        if property.units.exclude(kind=serializer.validated_data['kind']).exists():
            raise ValidationError('Use one inventory granularity per property: whole units, rooms or beds.')
        if property.units.count() >= 100:
            raise ValidationError('Pilot limit: 100 independently rentable spaces per property.')
        obj = serializer.save()
        changed(self.request.user, property, 'unit.created', unit_id=str(obj.pk))

    @transaction.atomic
    def perform_update(self, serializer):
        property = lock_property(self.request.user, serializer.instance.property_id)
        obj = Unit.objects.select_for_update().get(pk=serializer.instance.pk)
        if property.units.exclude(pk=obj.pk).exclude(kind=serializer.validated_data.get('kind', obj.kind)).exists():
            raise ValidationError('Changing this space would mix inventory granularities.')
        serializer.instance = obj
        obj = serializer.save()
        changed(self.request.user, property, 'unit.changed', unit_id=str(obj.pk), fields=sorted(serializer.validated_data))

    @action(detail=True, methods=['get', 'post'])
    def blocks(self, request, pk=None):
        unit = self.get_object()
        if request.method == 'GET':
            return Response(AvailabilitySerializer(unit.blocks.all(), many=True).data)
        data = AvailabilityInput(data=request.data)
        data.is_valid(raise_exception=True)
        obj = add_availability_block(request.user, unit, **data.validated_data)
        return Response(AvailabilitySerializer(obj).data, status=201)

    @action(detail=True, methods=['post'], url_path='cancel-block')
    @transaction.atomic
    def cancel_block(self, request, pk=None):
        unit = self.get_object()
        property = lock_property(request.user, unit.property_id)
        class CancelInput(serializers.Serializer):
            block_id = serializers.UUIDField()
        data = CancelInput(data=request.data)
        data.is_valid(raise_exception=True)
        block = get_object_or_404(AvailabilityBlock.objects.select_for_update(), pk=data.validated_data['block_id'], unit=unit)
        if block.cancelled:
            raise ValidationError('Block is already cancelled.')
        block.cancelled = True
        block.save(update_fields=['cancelled'])
        changed(request.user, property, 'availability.unblocked', block_id=str(block.pk))
        return Response(AvailabilitySerializer(block).data)


class ChargeViewSet(ConflictResponseMixin, mixins.CreateModelMixin, mixins.UpdateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ChargeSerializer

    def get_queryset(self):
        return UnitCharge.objects.filter(unit__property__in=managed_properties(self.request.user)).order_by('id')

    @transaction.atomic
    def perform_create(self, serializer):
        unit = serializer.validated_data['unit']
        property = lock_property(self.request.user, unit.property_id)
        if unit.charges.count() >= 20:
            raise ValidationError('Pilot limit: 20 disclosed charges per space.')
        obj = serializer.save()
        changed(self.request.user, property, 'charge.created', charge_id=str(obj.pk))

    @transaction.atomic
    def perform_update(self, serializer):
        property = lock_property(self.request.user, serializer.instance.unit.property_id)
        serializer.instance = UnitCharge.objects.select_for_update().get(pk=serializer.instance.pk)
        obj = serializer.save()
        changed(self.request.user, property, 'charge.changed', charge_id=str(obj.pk))


class MediaViewSet(ConflictResponseMixin, mixins.CreateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = MediaSerializer
    review_permission = 'properties.review_media'
    authentication_classes = [JWTAuthentication, SessionAuthentication]

    def get_queryset(self):
        user = self.request.user
        if can_review(user, self.review_permission) or can_review(user, 'properties.review_listing'):
            return PropertyMedia.objects.order_by('-created_at')
        scope = Q(property__in=managed_properties(user)) if user.is_authenticated else Q(pk__in=[])
        if self.action == 'file':
            scope |= Q(property__in=public_properties(), status=PropertyMedia.Status.APPROVED)
        return PropertyMedia.objects.filter(scope).order_by('-created_at')

    @transaction.atomic
    def perform_create(self, serializer):
        property = lock_property(self.request.user, serializer.validated_data['property'].pk)
        if property.media.count() >= 20:
            raise ValidationError('Pilot limit: 20 media files per property.')
        raw = serializer.validated_data.pop('file')
        validate = normalize_image if serializer.validated_data['kind'] == PropertyMedia.Kind.IMAGE else validate_video
        file, content_type, duration = validate(raw)
        obj = PropertyMedia(property=property, uploaded_by=self.request.user,
            kind=serializer.validated_data['kind'], caption=serializer.validated_data['caption'],
            sha256=digest(file), size=file.size, content_type=content_type, duration_seconds=duration)
        try:
            obj.file.save(file.name, file, save=False)
            obj.save()
            changed(self.request.user, property, 'media.uploaded', media_id=str(obj.pk))
        except Exception:
            if obj.file.name:
                obj.file.delete(save=False)
            raise
        serializer.instance = obj

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated, ReviewPermission])
    def review(self, request, pk=None):
        data = MediaReviewInput(data=request.data)
        data.is_valid(raise_exception=True)
        return Response(self.get_serializer(review_media(request.user, self.get_object(), **data.validated_data)).data)

    @action(detail=True, methods=['get'], permission_classes=[permissions.AllowAny])
    def file(self, request, pk=None):
        obj = self.get_object()
        response = FileResponse(obj.file.open('rb'), content_type=obj.content_type)
        response['Cache-Control'] = 'private, no-store'
        response['X-Content-Type-Options'] = 'nosniff'
        return response


class AmenityViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [permissions.AllowAny]
    serializer_class = AmenitySerializer
    queryset = Amenity.objects.order_by('name')
    pagination_class = RentalPagination


class ReportViewSet(ConflictResponseMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    from .serializers import ReportSerializer
    serializer_class = ReportSerializer
    permission_classes = [permissions.IsAuthenticated]
    review_permission = 'properties.review_listing'

    def get_queryset(self):
        rows = ListingReport.objects.order_by('-created_at')
        return rows if can_review(self.request.user, self.review_permission) else rows.filter(reporter=self.request.user)

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated, ReviewPermission])
    def resolve(self, request, pk=None):
        from .services import resolve_report
        class ResolutionInput(serializers.Serializer):
            reason = serializers.CharField(max_length=1000)
        data = ResolutionInput(data=request.data)
        data.is_valid(raise_exception=True)
        obj = resolve_report(request.user, self.get_object(), data.validated_data['reason'])
        return Response(self.get_serializer(obj).data)
