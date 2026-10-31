from django.db.models import Q
from rest_framework import serializers
from common.serializers import StrictModelSerializer
from .models import EvidenceDocument, PropertyAuthority, VerificationCase
from .services import current


class VerificationSerializer(StrictModelSerializer):
    class Meta:
        model = VerificationCase
        fields = ['id', 'applicant', 'role', 'status', 'expires_at', 'reviewed_by', 'review_note', 'created_at']
        read_only_fields = ['id', 'applicant', 'status', 'expires_at', 'reviewed_by', 'review_note', 'created_at']


class AuthoritySerializer(StrictModelSerializer):
    class Meta:
        model = PropertyAuthority
        fields = ['id', 'property', 'representative', 'verification', 'status', 'expires_at', 'reviewed_by', 'review_note', 'created_at']
        read_only_fields = ['id', 'representative', 'status', 'expires_at', 'reviewed_by', 'review_note', 'created_at']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            from properties.models import Property
            from properties.services import public_properties, managed_properties
            self.fields['verification'].queryset = current(VerificationCase.objects.filter(applicant=request.user))
            self.fields['property'].queryset = Property.objects.filter(Q(pk__in=managed_properties(request.user).values('pk')) | Q(pk__in=public_properties().values('pk')))
        else:
            self.fields['verification'].queryset = VerificationCase.objects.none()
            self.fields['property'].queryset = self.fields['property'].queryset.none()
        # The representative is assigned server-side, not a writable field.
        self.validators = []

    def validate(self, attrs):
        if PropertyAuthority.objects.filter(property=attrs['property'], representative=self.context['request'].user).exists():
            raise serializers.ValidationError('An authority request already exists for this property.')
        return attrs


class EvidenceInput(serializers.Serializer):
    case = serializers.UUIDField(required=False)
    authority = serializers.UUIDField(required=False)
    file = serializers.FileField()

    def validate(self, attrs):
        if ('case' in attrs) == ('authority' in attrs):
            raise serializers.ValidationError('Provide exactly one case or authority.')
        return attrs


class EvidenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = EvidenceDocument
        fields = ['id', 'case', 'authority', 'content_type', 'sha256', 'size', 'created_at']
        read_only_fields = fields
