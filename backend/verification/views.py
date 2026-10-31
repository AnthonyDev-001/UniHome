from django.db import transaction
from django.db.models import Q
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from rest_framework import mixins, permissions, viewsets
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication

from audit.models import record
from common.permissions import ReviewPermission, can_review
from common.serializers import ReviewInput
from common.uploads import digest, normalize_evidence
from common.views import ConflictResponseMixin
from .models import EvidenceDocument, PropertyAuthority, ReviewStatus, VerificationCase
from .serializers import AuthoritySerializer, EvidenceInput, EvidenceSerializer, VerificationSerializer
from .services import current, lock_user, review, submit_review


class ReviewViewSet(ConflictResponseMixin, mixins.CreateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        obj = submit_review(request.user, self.get_object())
        return Response(self.get_serializer(obj).data)

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated, ReviewPermission])
    def review(self, request, pk=None):
        obj = self.get_object()
        data = ReviewInput(data=request.data)
        data.is_valid(raise_exception=True)
        obj = review(request.user, obj, **data.validated_data)
        return Response(self.get_serializer(obj).data)


class VerificationViewSet(ReviewViewSet):
    serializer_class = VerificationSerializer
    review_permission = 'verification.review_verification'

    def get_queryset(self):
        rows = VerificationCase.objects.order_by('-created_at')
        return rows if can_review(self.request.user, self.review_permission) else rows.filter(applicant=self.request.user)

    @transaction.atomic
    def perform_create(self, serializer):
        lock_user(self.request.user.pk)
        obj = serializer.save(applicant=self.request.user)
        record(self.request.user, 'verification.created', obj, role=obj.role)


class AuthorityViewSet(ReviewViewSet):
    serializer_class = AuthoritySerializer
    review_permission = 'verification.review_authority'

    def get_queryset(self):
        rows = PropertyAuthority.objects.order_by('-created_at')
        return rows if can_review(self.request.user, self.review_permission) else rows.filter(representative=self.request.user)

    @transaction.atomic
    def perform_create(self, serializer):
        lock_user(self.request.user.pk)
        verification = serializer.validated_data['verification']
        if not current(VerificationCase.objects.filter(pk=verification.pk, applicant=self.request.user)).exists():
            raise ValidationError('A current identity approval is required.')
        obj = serializer.save(representative=self.request.user)
        record(self.request.user, 'authority.created', obj, property_id=str(obj.property_id))


class EvidenceViewSet(ConflictResponseMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = EvidenceSerializer
    # Sessions allow authorized Django admin users to download attached evidence.
    authentication_classes = [JWTAuthentication, SessionAuthentication]

    def get_queryset(self):
        user = self.request.user
        scope = Q(case__applicant=user) | Q(authority__representative=user)
        if can_review(user, 'verification.review_verification'):
            scope |= Q(case__isnull=False)
        if can_review(user, 'verification.review_authority'):
            scope |= Q(authority__isnull=False)
        return EvidenceDocument.objects.filter(scope).order_by('-created_at')

    @transaction.atomic
    def create(self, request):
        data = EvidenceInput(data=request.data)
        data.is_valid(raise_exception=True)
        lock_user(request.user.pk)
        key = 'case' if 'case' in data.validated_data else 'authority'
        model = VerificationCase if key == 'case' else PropertyAuthority
        owner_field = 'applicant' if key == 'case' else 'representative'
        parent = get_object_or_404(model.objects.select_for_update(), pk=data.validated_data[key], **{owner_field: request.user})
        if parent.status not in {ReviewStatus.DRAFT, ReviewStatus.REJECTED}:
            raise ValidationError('Evidence can only be added to draft or rejected requests.')
        if parent.documents.count() >= 10:
            raise ValidationError('Pilot limit: 10 evidence documents per request.')
        file, content_type, _ = normalize_evidence(data.validated_data['file'])
        obj = EvidenceDocument(**{key: parent}, content_type=content_type, sha256=digest(file), size=file.size)
        try:
            obj.file.save(file.name, file, save=False)
            obj.save()
            record(request.user, 'evidence.uploaded', obj, parent_id=str(parent.pk))
        except Exception:
            if obj.file.name:
                obj.file.delete(save=False)
            raise
        return Response(EvidenceSerializer(obj).data, status=201)

    @action(detail=True, methods=['get'])
    def file(self, request, pk=None):
        obj = self.get_object()
        record(request.user, 'evidence.downloaded', obj)
        response = FileResponse(obj.file.open('rb'), as_attachment=True, filename=f'evidence-{obj.pk}', content_type='application/octet-stream')
        response['Cache-Control'] = 'private, no-store'
        response['X-Content-Type-Options'] = 'nosniff'
        return response
