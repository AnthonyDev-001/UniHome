from datetime import timedelta
from decimal import Decimal
from django.utils import timezone
from rest_framework import serializers
from rest_framework.reverse import reverse

from common.serializers import StrictModelSerializer
from .models import Amenity, AvailabilityBlock, Property, PropertyMedia, Unit, UnitCharge
from .services import managed_properties, unit_available


class AmenitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Amenity
        fields = ['id', 'name', 'slug']


class ScopedParentMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get('request')
        rows = managed_properties(request.user) if request and request.user.is_authenticated else Property.objects.none()
        if 'property' in self.fields and not self.fields['property'].read_only:
            self.fields['property'].queryset = rows
        if 'unit' in self.fields and not self.fields['unit'].read_only:
            self.fields['unit'].queryset = Unit.objects.filter(property__in=rows)

    def validate(self, attrs):
        if self.instance:
            for parent in ['property', 'unit']:
                if parent in attrs and getattr(self.instance, f'{parent}_id') != attrs[parent].pk:
                    raise serializers.ValidationError({parent: 'Parent cannot be changed.'})
        return attrs


class ChargeSerializer(ScopedParentMixin, StrictModelSerializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('0.00'))
    refundable = serializers.BooleanField(required=True)
    recurring = serializers.BooleanField(required=True)

    class Meta:
        model = UnitCharge
        fields = ['id', 'unit', 'kind', 'label', 'amount', 'refundable', 'recurring']
        read_only_fields = ['id']


class UnitSerializer(ScopedParentMixin, StrictModelSerializer):
    rent = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('0.01'))
    capacity = serializers.IntegerField(min_value=1, max_value=20, default=1)
    charges = ChargeSerializer(many=True, read_only=True)

    class Meta:
        model = Unit
        fields = ['id', 'property', 'label', 'kind', 'capacity', 'rent', 'billing_period', 'currency', 'status', 'available_from', 'charges']
        read_only_fields = ['id', 'currency', 'charges']

    def validate(self, attrs):
        attrs = super().validate(attrs)
        kind = attrs.get('kind', getattr(self.instance, 'kind', None))
        capacity = attrs.get('capacity', getattr(self.instance, 'capacity', 1))
        if kind == Unit.Kind.BED and capacity != 1:
            raise serializers.ValidationError({'capacity': 'A bed is a single rentable space.'})
        return attrs


class MediaSerializer(ScopedParentMixin, StrictModelSerializer):
    file = serializers.FileField(write_only=True)

    class Meta:
        model = PropertyMedia
        fields = ['id', 'property', 'kind', 'caption', 'file', 'status', 'content_type', 'size', 'sha256', 'duration_seconds', 'reviewed_by', 'review_note', 'created_at']
        read_only_fields = ['id', 'status', 'content_type', 'size', 'sha256', 'duration_seconds', 'reviewed_by', 'review_note', 'created_at']


class PropertySerializer(StrictModelSerializer):
    units = UnitSerializer(many=True, read_only=True)
    media = MediaSerializer(many=True, read_only=True)

    class Meta:
        model = Property
        fields = ['id', 'created_by', 'publisher', 'title', 'description', 'category', 'state', 'city', 'area', 'campus', 'private_address', 'rules', 'amenities', 'status', 'revision', 'approved_revision', 'units', 'media', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_by', 'publisher', 'status', 'revision', 'approved_revision', 'units', 'media', 'created_at', 'updated_at']


class PublicChargeSerializer(serializers.ModelSerializer):
    class Meta:
        model = UnitCharge
        fields = ['kind', 'label', 'amount', 'refundable', 'recurring']


class PublicUnitSerializer(serializers.ModelSerializer):
    charges = PublicChargeSerializer(many=True, read_only=True)
    total_first_period = serializers.SerializerMethodField()
    available_today = serializers.SerializerMethodField()

    class Meta:
        model = Unit
        fields = ['id', 'label', 'kind', 'capacity', 'rent', 'billing_period', 'currency', 'status', 'available_from', 'charges', 'total_first_period', 'available_today']

    def get_total_first_period(self, obj):
        # Includes one-off charges and one occurrence of per-period charges.
        return format(obj.rent + sum((c.amount for c in obj.charges.all()), Decimal('0.00')), '.2f')

    def get_available_today(self, obj):
        today = timezone.localdate(timezone=timezone.get_fixed_timezone(60))
        return unit_available(obj, today, today + timedelta(days=1))


class PublicMediaSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = PropertyMedia
        fields = ['id', 'kind', 'caption', 'size', 'duration_seconds', 'url']

    def get_url(self, obj):
        return reverse('property-media-file', args=[obj.pk], request=self.context.get('request'))


class PublicPropertySerializer(serializers.ModelSerializer):
    amenities = AmenitySerializer(many=True, read_only=True)
    units = PublicUnitSerializer(many=True, read_only=True)
    media = serializers.SerializerMethodField()
    verification = serializers.SerializerMethodField()

    class Meta:
        model = Property
        fields = ['id', 'title', 'description', 'category', 'state', 'city', 'area', 'campus', 'rules', 'amenities', 'units', 'media', 'verification']

    def get_media(self, obj):
        return PublicMediaSerializer(obj.media.filter(status=PropertyMedia.Status.APPROVED), many=True, context=self.context).data

    def get_verification(self, obj):
        return {'representative_identity_reviewed': True, 'listing_authority_reviewed': True,
                'meaning': 'Documents reviewed by staff; not a title guarantee or a substitute for inspection.'}


class AvailabilityInput(serializers.Serializer):
    starts_on = serializers.DateField()
    ends_on = serializers.DateField()
    reason = serializers.CharField(max_length=300)


class AvailabilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = AvailabilityBlock
        fields = ['id', 'unit', 'starts_on', 'ends_on', 'reason', 'cancelled']


class SearchInput(serializers.Serializer):
    category = serializers.ChoiceField(choices=Property.Category.choices, required=False)
    city = serializers.CharField(max_length=100, required=False)
    area = serializers.CharField(max_length=100, required=False)
    campus = serializers.CharField(max_length=160, required=False)
    kind = serializers.ChoiceField(choices=Unit.Kind.choices, required=False)
    billing_period = serializers.ChoiceField(choices=Unit.Period.choices, required=False)
    min_rent = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0, required=False)
    max_rent = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0, required=False)
    available_on = serializers.DateField(required=False)

    def validate(self, attrs):
        if ('min_rent' in attrs or 'max_rent' in attrs) and 'billing_period' not in attrs:
            raise serializers.ValidationError('Price filters require a billing_period.')
        if attrs.get('min_rent', 0) > attrs.get('max_rent', Decimal('9999999999.99')):
            raise serializers.ValidationError('min_rent exceeds max_rent.')
        return attrs


from .models import ListingReport


class ReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = ListingReport
        fields = ['id', 'property', 'reason', 'details', 'resolved', 'resolution_note', 'created_at']
        read_only_fields = fields
