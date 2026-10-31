import uuid
from django.conf import settings
from django.db import models
from common.storage import private_storage, private_path


class Amenity(models.Model):
    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(unique=True)

    def __str__(self):
        return self.name


class Property(models.Model):
    class Category(models.TextChoices):
        STUDENT = 'STUDENT', 'Student accommodation'
        RESIDENTIAL = 'RESIDENTIAL', 'Long-term residential'

    class Status(models.TextChoices):
        DRAFT = 'DRAFT', 'Draft'
        PENDING = 'PENDING_REVIEW', 'Pending review'
        ACTIVE = 'ACTIVE', 'Active'
        REJECTED = 'REJECTED', 'Rejected'
        SUSPENDED = 'SUSPENDED', 'Suspended'
        UNAVAILABLE = 'UNAVAILABLE', 'Unavailable'
        ARCHIVED = 'ARCHIVED', 'Archived'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='created_properties')
    publisher = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name='published_properties')
    title = models.CharField(max_length=180)
    description = models.TextField(max_length=10000)
    category = models.CharField(max_length=16, choices=Category.choices)
    state = models.CharField(max_length=80)
    city = models.CharField(max_length=100)
    area = models.CharField(max_length=100)
    campus = models.CharField(max_length=160, blank=True)
    private_address = models.CharField(max_length=500)
    rules = models.TextField(max_length=3000, blank=True)
    amenities = models.ManyToManyField(Amenity, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    revision = models.PositiveIntegerField(default=1)
    approved_revision = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        permissions = [('review_listing', 'Review and suspend rental listings')]
        ordering = ['-created_at', 'id']

    def __str__(self):
        return self.title


class Unit(models.Model):
    class Kind(models.TextChoices):
        UNIT = 'UNIT', 'Self-contained unit'
        ROOM = 'ROOM', 'Room'
        BED = 'BED', 'Bed'

    class Period(models.TextChoices):
        MONTH = 'MONTH', 'Month'
        SEMESTER = 'SEMESTER', 'Semester'
        YEAR = 'YEAR', 'Year'

    class Status(models.TextChoices):
        AVAILABLE = 'AVAILABLE', 'Available'
        UNAVAILABLE = 'UNAVAILABLE', 'Unavailable'
        OCCUPIED = 'OCCUPIED', 'Occupied'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    property = models.ForeignKey(Property, on_delete=models.PROTECT, related_name='units')
    label = models.CharField(max_length=100)
    kind = models.CharField(max_length=10, choices=Kind.choices)
    capacity = models.PositiveSmallIntegerField(default=1)
    rent = models.DecimalField(max_digits=12, decimal_places=2)
    billing_period = models.CharField(max_length=12, choices=Period.choices)
    currency = models.CharField(max_length=3, default='NGN', editable=False)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.AVAILABLE)
    available_from = models.DateField()

    class Meta:
        ordering = ['label', 'id']
        constraints = [
            models.UniqueConstraint(fields=['property', 'label'], name='unique_property_unit_label'),
            models.CheckConstraint(condition=models.Q(rent__gt=0), name='unit_positive_rent'),
            models.CheckConstraint(condition=models.Q(capacity__gte=1) & models.Q(capacity__lte=20), name='unit_capacity_range'),
            models.CheckConstraint(condition=~models.Q(kind='BED') | models.Q(capacity=1), name='bed_single_capacity'),
        ]


class UnitCharge(models.Model):
    class Kind(models.TextChoices):
        DEPOSIT = 'DEPOSIT', 'Deposit'
        AGENT = 'AGENT', 'Agent fee'
        SERVICE = 'SERVICE', 'Service fee'
        UTILITY = 'UTILITY', 'Utilities'
        OTHER = 'OTHER', 'Other disclosed charge'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    unit = models.ForeignKey(Unit, on_delete=models.PROTECT, related_name='charges')
    kind = models.CharField(max_length=12, choices=Kind.choices)
    label = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    refundable = models.BooleanField()
    recurring = models.BooleanField()  # Per stated rent period, otherwise one-off.

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(amount__gte=0), name='nonnegative_unit_charge')]


class AvailabilityBlock(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    unit = models.ForeignKey(Unit, on_delete=models.PROTECT, related_name='blocks')
    starts_on = models.DateField()
    ends_on = models.DateField()  # Exclusive end, permits adjacent intervals.
    reason = models.CharField(max_length=300)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    cancelled = models.BooleanField(default=False)

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(ends_on__gt=models.F('starts_on')), name='valid_availability_interval')]


class PropertyMedia(models.Model):
    class Kind(models.TextChoices):
        IMAGE = 'IMAGE', 'Image'
        VIDEO = 'VIDEO', 'Video tour'

    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending review'
        APPROVED = 'APPROVED', 'Approved'
        REJECTED = 'REJECTED', 'Rejected'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    property = models.ForeignKey(Property, on_delete=models.PROTECT, related_name='media')
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    kind = models.CharField(max_length=10, choices=Kind.choices)
    caption = models.CharField(max_length=300)
    file = models.FileField(storage=private_storage, upload_to=private_path)
    content_type = models.CharField(max_length=80)
    sha256 = models.CharField(max_length=64)
    size = models.PositiveIntegerField()
    duration_seconds = models.FloatField(default=0)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name='media_reviews')
    review_note = models.CharField(max_length=1000, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        permissions = [('review_media', 'Review property media for publication')]


class ListingRevision(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    property = models.ForeignKey(Property, on_delete=models.PROTECT, related_name='submissions')
    number = models.PositiveIntegerField()
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    snapshot = models.JSONField()
    sha256 = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['property', 'number'], name='unique_listing_revision')]
        default_permissions = ('view',)

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError('Submitted revisions are immutable.')
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError('Submitted revisions cannot be deleted.')


class ListingReport(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    property = models.ForeignKey(Property, on_delete=models.PROTECT, related_name='reports')
    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    reason = models.CharField(max_length=40, choices=[('FRAUD', 'Suspected fraud'), ('MISLEADING', 'Misleading content'), ('UNAVAILABLE', 'Unavailable'), ('OTHER', 'Other')])
    details = models.CharField(max_length=2000)
    resolved = models.BooleanField(default=False)
    resolution_note = models.CharField(max_length=1000, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
