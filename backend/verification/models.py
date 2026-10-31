import uuid
from django.conf import settings
from django.db import models
from common.storage import private_storage, private_path


class ReviewStatus(models.TextChoices):
    DRAFT = 'DRAFT', 'Draft'
    PENDING = 'PENDING', 'Pending review'
    APPROVED = 'APPROVED', 'Approved'
    REJECTED = 'REJECTED', 'Rejected'
    SUSPENDED = 'SUSPENDED', 'Suspended'


class VerificationCase(models.Model):
    class Role(models.TextChoices):
        AGENT = 'AGENT', 'Agent'
        LANDLORD = 'LANDLORD', 'Landlord'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    applicant = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    role = models.CharField(max_length=16, choices=Role.choices)
    status = models.CharField(max_length=16, choices=ReviewStatus.choices, default=ReviewStatus.DRAFT)
    expires_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name='identity_reviews')
    review_note = models.CharField(max_length=1000, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['applicant', 'role'], name='unique_applicant_role')]
        permissions = [('review_verification', 'Review representative identity')]


class PropertyAuthority(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    property = models.ForeignKey('properties.Property', on_delete=models.PROTECT, related_name='authorities')
    representative = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    verification = models.ForeignKey(VerificationCase, on_delete=models.PROTECT)
    status = models.CharField(max_length=16, choices=ReviewStatus.choices, default=ReviewStatus.DRAFT)
    expires_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name='authority_reviews')
    review_note = models.CharField(max_length=1000, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['property', 'representative'], name='unique_property_representative')]
        permissions = [('review_authority', 'Review documentary authority to list')]


class EvidenceDocument(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    case = models.ForeignKey(VerificationCase, null=True, blank=True, on_delete=models.PROTECT, related_name='documents')
    authority = models.ForeignKey(PropertyAuthority, null=True, blank=True, on_delete=models.PROTECT, related_name='documents')
    file = models.FileField(storage=private_storage, upload_to=private_path)
    content_type = models.CharField(max_length=80)
    sha256 = models.CharField(max_length=64)
    size = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=(models.Q(case__isnull=False, authority__isnull=True) | models.Q(case__isnull=True, authority__isnull=False)), name='evidence_exactly_one_parent')]
