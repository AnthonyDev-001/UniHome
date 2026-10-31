import hashlib
import json

from django.db import transaction
from django.db.models import Exists, F, OuterRef, Q
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from audit.models import record
from common.permissions import can_review
from verification.services import valid_authorities, require_representative, lock_user
from .models import AvailabilityBlock, ListingRevision, Property, PropertyMedia, Unit


def public_properties():
    authority = valid_authorities().filter(property_id=OuterRef('pk'), representative_id=OuterRef('publisher_id'))
    return Property.objects.filter(status=Property.Status.ACTIVE, approved_revision=F('revision'), publisher__is_active=True).annotate(
        current_authority=Exists(authority),
    ).filter(current_authority=True)


def managed_properties(user):
    return Property.objects.filter(Q(created_by=user) | Q(pk__in=valid_authorities().filter(representative=user).values('property_id'))).distinct()


def lock_property(actor, property_id):
    lock_user(actor.pk)
    property = Property.objects.select_for_update().get(pk=property_id)
    require_representative(actor, property)
    if property.status == Property.Status.ARCHIVED:
        raise ValidationError('Archived listings cannot be changed.')
    return property


def changed(actor, property, action, **metadata):
    previous = property.status
    property.revision += 1
    # Content changes can never lift a moderator's suspension.
    if property.status != Property.Status.SUSPENDED:
        property.status = Property.Status.DRAFT
    property.save(update_fields=['revision', 'status', 'updated_at'])
    record(actor, action, property, previous=previous, status=property.status, revision=property.revision, **metadata)


def snapshot(property):
    return {
        **{field: getattr(property, field) for field in ['title', 'description', 'category', 'state', 'city', 'area', 'campus', 'private_address', 'rules']},
        'amenities': list(property.amenities.order_by('pk').values('id', 'name', 'slug')),
        'units': [
            {**{field: str(getattr(unit, field)) for field in ['id', 'label', 'kind', 'capacity', 'rent', 'billing_period', 'currency', 'status', 'available_from']},
             'charges': list(unit.charges.order_by('id').values('id', 'kind', 'label', 'amount', 'refundable', 'recurring')),
             'blocks': list(unit.blocks.filter(cancelled=False).order_by('id').values('id', 'starts_on', 'ends_on'))}
            for unit in property.units.order_by('id')
        ],
        'media': list(property.media.filter(status=PropertyMedia.Status.APPROVED).order_by('id').values('id', 'kind', 'caption', 'sha256')),
    }


def canonical(value):
    # UUID/Decimal/date normalization keeps snapshots portable across DB engines.
    return json.dumps(value, sort_keys=True, separators=(',', ':'), default=str)


@transaction.atomic
def submit_listing(actor, obj):
    property = lock_property(actor, obj.pk)
    if property.status not in {Property.Status.DRAFT, Property.Status.REJECTED, Property.Status.UNAVAILABLE}:
        raise ValidationError('Only draft, rejected or unavailable listings can be submitted.')
    if not valid_authorities().filter(property=property, representative=actor).exists():
        raise ValidationError('Current identity and property-authority approvals are required.')
    if not property.units.filter(status=Unit.Status.AVAILABLE).exists():
        raise ValidationError('At least one available unit is required.')
    if not property.media.filter(status=PropertyMedia.Status.APPROVED, kind=PropertyMedia.Kind.IMAGE).exists() or not property.media.filter(status=PropertyMedia.Status.APPROVED, kind=PropertyMedia.Kind.VIDEO).exists():
        raise ValidationError('An approved image and video tour are required.')
    encoded = canonical(snapshot(property))
    if ListingRevision.objects.filter(property=property, number=property.revision).exists():
        property.revision += 1  # Re-submission without content changes is a new review record.
    ListingRevision.objects.create(property=property, number=property.revision, submitted_by=actor,
                                   snapshot=json.loads(encoded), sha256=hashlib.sha256(encoded.encode()).hexdigest())
    property.publisher, property.status = actor, Property.Status.PENDING
    property.save(update_fields=['publisher', 'status', 'revision', 'updated_at'])
    record(actor, 'listing.submitted', property, revision=property.revision)
    return property


@transaction.atomic
def review_listing(actor, obj, decision, reason, expected_revision):
    if not can_review(actor, 'properties.review_listing'):
        raise PermissionDenied()
    owner_id = obj.publisher_id or obj.created_by_id
    lock_user(owner_id)
    property = Property.objects.select_for_update().get(pk=obj.pk)
    if actor.pk in {property.created_by_id, property.publisher_id} or valid_authorities().filter(property=property, representative=actor).exists():
        raise PermissionDenied('You cannot moderate your own or represented listing.')
    if property.revision != expected_revision or (property.publisher_id or property.created_by_id) != owner_id:
        raise ValidationError('Listing changed; reload and review the current revision.')
    if decision == 'APPROVED':
        if property.status != Property.Status.PENDING:
            raise ValidationError('Only pending listings can be approved.')
        if not valid_authorities().filter(property=property, representative_id=property.publisher_id).exists():
            raise ValidationError('Representative approval is no longer current.')
        revision = ListingRevision.objects.get(property=property, number=property.revision)
        if hashlib.sha256(canonical(snapshot(property)).encode()).hexdigest() != revision.sha256:
            raise ValidationError('Listing content changed since submission.')
        property.approved_revision = property.revision
        next_status = Property.Status.ACTIVE
    elif decision == 'REJECTED' and property.status == Property.Status.PENDING:
        next_status = Property.Status.REJECTED
    elif decision == 'SUSPENDED' and property.status not in {Property.Status.ARCHIVED, Property.Status.SUSPENDED}:
        next_status = Property.Status.SUSPENDED
    elif decision == 'REOPEN' and property.status == Property.Status.SUSPENDED:
        next_status = Property.Status.DRAFT
    else:
        raise ValidationError('Invalid listing transition.')
    previous = property.status
    property.status = next_status
    property.save(update_fields=['status', 'approved_revision', 'updated_at'])
    record(actor, 'listing.reviewed', property, reason, previous=previous, status=next_status, revision=property.revision)
    return property


@transaction.atomic
def review_media(actor, obj, decision, reason):
    if not can_review(actor, 'properties.review_media'):
        raise PermissionDenied()
    lock_user(obj.uploaded_by_id)
    property = Property.objects.select_for_update().get(pk=obj.property_id)
    obj = PropertyMedia.objects.select_for_update().get(pk=obj.pk)
    if actor.pk in {obj.uploaded_by_id, property.created_by_id} or valid_authorities().filter(property=property, representative=actor).exists():
        raise PermissionDenied('You cannot review your own property media.')
    if decision not in {'APPROVED', 'REJECTED'} or (obj.status != PropertyMedia.Status.PENDING and not (obj.status == PropertyMedia.Status.APPROVED and decision == 'REJECTED')):
        raise ValidationError('Invalid media review transition.')
    obj.status, obj.reviewed_by, obj.review_note = decision, actor, reason
    obj.save(update_fields=['status', 'reviewed_by', 'review_note'])
    if property.status in {Property.Status.ACTIVE, Property.Status.PENDING}:
        property.status = Property.Status.SUSPENDED
    changed(actor, property, 'media.reviewed', media_id=str(obj.pk), media_status=decision)
    record(actor, 'media.decision', obj, reason, status=decision)
    return obj


def unit_available(unit, starts_on, ends_on):
    return (unit.status == Unit.Status.AVAILABLE and unit.available_from <= starts_on and starts_on < ends_on
            and not unit.blocks.filter(cancelled=False, starts_on__lt=ends_on, ends_on__gt=starts_on).exists())


@transaction.atomic
def add_availability_block(actor, unit, starts_on, ends_on, reason):
    property = lock_property(actor, unit.property_id)
    unit = Unit.objects.select_for_update().get(pk=unit.pk)
    if ends_on <= starts_on:
        raise ValidationError('End date must be after start date.')
    if unit.blocks.filter(cancelled=False, starts_on__lt=ends_on, ends_on__gt=starts_on).exists():
        raise ValidationError('This interval overlaps an existing availability block.')
    block = AvailabilityBlock.objects.create(unit=unit, starts_on=starts_on, ends_on=ends_on, reason=reason, created_by=actor)
    changed(actor, property, 'availability.blocked', block_id=str(block.pk))
    return block


@transaction.atomic
def resolve_report(actor, report, reason):
    from .models import ListingReport
    if not can_review(actor, 'properties.review_listing'):
        raise PermissionDenied()
    report = ListingReport.objects.select_for_update().get(pk=report.pk)
    if report.resolved:
        raise ValidationError('Report is already resolved.')
    if actor.pk == report.reporter_id or is_property_party(actor, report.property):
        raise PermissionDenied('A party to this report cannot resolve it.')
    report.resolved, report.resolution_note = True, reason
    report.save(update_fields=['resolved', 'resolution_note'])
    record(actor, 'report.resolved', report, reason)
    return report


def is_property_party(actor, property):
    return actor.pk in {property.created_by_id, property.publisher_id} or valid_authorities().filter(property=property, representative=actor).exists()
