from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from audit.models import record
from common.permissions import can_review
from .models import PropertyAuthority, ReviewStatus, VerificationCase


def current(queryset):
    return queryset.filter(status=ReviewStatus.APPROVED).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now()))


def valid_authorities():
    return current(PropertyAuthority.objects.all()).filter(
        representative__is_active=True, verification__status=ReviewStatus.APPROVED, verification__applicant_id=F("representative_id"),
    ).filter(Q(verification__expires_at__isnull=True) | Q(verification__expires_at__gt=timezone.now()))


def lock_user(user_id):
    return get_user_model().objects.select_for_update().get(pk=user_id)


def is_representative(user, property):
    return user.is_authenticated and (property.created_by_id == user.pk or valid_authorities().filter(property=property, representative=user).exists())


def require_representative(user, property):
    if not is_representative(user, property):
        raise PermissionDenied('You cannot manage this property.')


@transaction.atomic
def submit_review(actor, obj):
    lock_user(actor.pk)
    obj = type(obj).objects.select_for_update().get(pk=obj.pk)
    owner_id = obj.applicant_id if isinstance(obj, VerificationCase) else obj.representative_id
    if owner_id != actor.pk:
        raise PermissionDenied()
    if obj.status not in {ReviewStatus.DRAFT, ReviewStatus.REJECTED}:
        raise ValidationError('This request cannot be submitted in its current state.')
    if not obj.documents.exists():
        raise ValidationError('At least one evidence document is required.')
    if isinstance(obj, PropertyAuthority) and not current(VerificationCase.objects.filter(pk=obj.verification_id, applicant=actor)).exists():
        raise ValidationError('An active identity review is required before submitting property authority.')
    previous = obj.status
    obj.status = ReviewStatus.PENDING
    obj.review_note = ''
    obj.save(update_fields=['status', 'review_note'])
    record(actor, 'verification.submitted', obj, previous=previous, status=obj.status)
    return obj


@transaction.atomic
def review(actor, obj, decision, reason, expires_at=None):
    from properties.models import Property
    permission = 'verification.review_verification' if isinstance(obj, VerificationCase) else 'verification.review_authority'
    if not can_review(actor, permission):
        raise PermissionDenied()
    owner_id = obj.applicant_id if isinstance(obj, VerificationCase) else obj.representative_id
    if actor.pk == owner_id:
        raise PermissionDenied('You cannot review your own identity or authority.')
    lock_user(owner_id)
    # Consistent user -> property -> review row order with listing transitions.
    if isinstance(obj, PropertyAuthority):
        Property.objects.select_for_update().get(pk=obj.property_id)
    obj = type(obj).objects.select_for_update().get(pk=obj.pk)
    if expires_at is not None and expires_at <= timezone.now():
        raise ValidationError({'expires_at': 'Expiry must be in the future.'})
    if decision in {ReviewStatus.APPROVED, ReviewStatus.REJECTED}:
        if obj.status != ReviewStatus.PENDING:
            raise ValidationError('Only pending requests can be approved or rejected.')
        if decision == ReviewStatus.APPROVED:
            if not obj.documents.exists():
                raise ValidationError('Evidence is required.')
            if isinstance(obj, PropertyAuthority) and not current(VerificationCase.objects.filter(pk=obj.verification_id, applicant_id=owner_id)).exists():
                raise ValidationError('Representative identity review is not current.')
    elif decision == ReviewStatus.SUSPENDED:
        if obj.status != ReviewStatus.APPROVED:
            raise ValidationError('Only approved requests can be suspended.')
    elif decision == 'REOPEN':
        if obj.status != ReviewStatus.SUSPENDED and not (obj.status == ReviewStatus.APPROVED and obj.expires_at and obj.expires_at <= timezone.now()):
            raise ValidationError('Only suspended or expired requests can be reopened.')
        decision = ReviewStatus.DRAFT
    else:
        raise ValidationError('Unsupported review decision.')
    previous = obj.status
    obj.status, obj.review_note, obj.reviewed_by = decision, reason, actor
    obj.expires_at = expires_at if decision == ReviewStatus.APPROVED else obj.expires_at
    obj.save(update_fields=['status', 'review_note', 'reviewed_by', 'expires_at'])
    record(actor, 'verification.reviewed', obj, reason, previous=previous, status=decision)
    if decision != ReviewStatus.APPROVED:
        affected = Property.objects.select_for_update().filter(publisher_id=owner_id, status__in=[Property.Status.ACTIVE, Property.Status.PENDING])
        if isinstance(obj, PropertyAuthority):
            affected = affected.filter(pk=obj.property_id)
        else:
            affected = affected.filter(pk__in=PropertyAuthority.objects.filter(verification=obj, representative_id=owner_id).values('property_id'))
        for property in affected.order_by('pk'):
            property.status = Property.Status.SUSPENDED
            property.save(update_fields=['status', 'updated_at'])
            record(actor, 'listing.suspended', property, 'Representative review is no longer active.', review_id=str(obj.pk))
    return obj
