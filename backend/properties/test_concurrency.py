import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from unittest import skipUnless

from django.contrib.auth.models import Permission, User
from django.db import close_old_connections, connection
from django.test import TransactionTestCase
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from verification.models import PropertyAuthority, VerificationCase
from verification.services import review
from .models import AvailabilityBlock, ListingRevision, Property, PropertyMedia, Unit
from .services import add_availability_block, canonical, public_properties, review_listing, snapshot


@skipUnless(connection.vendor == 'postgresql', 'Concurrency requires PostgreSQL row locks')
class InventoryConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.owner = User.objects.create_user('inventory-owner')
        self.reviewer = User.objects.create_user('inventory-reviewer', is_staff=True)
        self.reviewer.user_permissions.set(Permission.objects.filter(codename__in=['review_verification', 'review_listing']))
        self.property = Property.objects.create(created_by=self.owner, title='Test', description='Synthetic', category='STUDENT', state='Test', city='Test', area='Test', private_address='Private')
        self.unit = Unit.objects.create(property=self.property, label='A', kind='ROOM', rent='100.00', billing_period='MONTH', available_from=timezone.now().date())

    def race(self, first, second):
        barrier = Barrier(2)
        def worker(fn):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                try:
                    return fn()
                except ValidationError:
                    return 400
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(worker, fn) for fn in [first, second]]
            return [future.result(timeout=30) for future in futures]

    def test_overlapping_availability_blocks_cannot_both_succeed(self):
        def block():
            owner = User.objects.get(pk=self.owner.pk)
            unit = Unit.objects.get(pk=self.unit.pk)
            day = timezone.now().date()
            add_availability_block(owner, unit, day, day + timedelta(days=3), 'Synthetic maintenance')
            return 201
        self.assertEqual(sorted(self.race(block, block)), [201, 400])
        self.assertEqual(AvailabilityBlock.objects.count(), 1)
        self.property.refresh_from_db()
        self.assertEqual(self.property.revision, 2)

    def test_simultaneous_edits_preserve_fields_and_revision_increments(self):
        def edit(data):
            client = APIClient()
            client.force_authenticate(User.objects.get(pk=self.owner.pk))
            return client.patch(f'/api/v1/management/properties/{self.property.pk}/', data, format='json').status_code
        self.assertEqual(self.race(lambda: edit({'title': 'New title'}), lambda: edit({'description': 'New description'})), [200, 200])
        self.property.refresh_from_db()
        self.assertEqual(self.property.revision, 3)
        self.assertEqual(self.property.title, 'New title')
        self.assertEqual(self.property.description, 'New description')

    def test_identity_revocation_racing_approval_never_leaves_public_listing(self):
        case = VerificationCase.objects.create(applicant=self.owner, role='AGENT', status='APPROVED')
        PropertyAuthority.objects.create(property=self.property, representative=self.owner, verification=case, status='APPROVED')
        for kind in ['IMAGE', 'VIDEO']:
            # Race fixtures concern immutable metadata; file parsing is tested via the real API suite.
            PropertyMedia.objects.create(property=self.property, uploaded_by=self.owner, kind=kind, caption='Synthetic', file='not-served', content_type='image/jpeg' if kind == 'IMAGE' else 'video/mp4', sha256='0'*64, size=1, status='APPROVED')
        self.property.publisher = self.owner
        self.property.status = 'PENDING_REVIEW'
        self.property.save()
        encoded = canonical(snapshot(self.property))
        ListingRevision.objects.create(property=self.property, number=1, submitted_by=self.owner, snapshot=json.loads(encoded), sha256=hashlib.sha256(encoded.encode()).hexdigest())
        def approve():
            review_listing(User.objects.get(pk=self.reviewer.pk), Property.objects.get(pk=self.property.pk), 'APPROVED', 'Synthetic approval', 1)
            return 200
        def suspend():
            review(User.objects.get(pk=self.reviewer.pk), VerificationCase.objects.get(pk=case.pk), 'SUSPENDED', 'Synthetic revocation')
            return 200
        results = self.race(approve, suspend)
        self.assertIn(results[0], [200, 400])
        self.assertEqual(results[1], 200)
        self.property.refresh_from_db()
        self.assertEqual(self.property.status, 'SUSPENDED')
        self.assertFalse(public_properties().filter(pk=self.property.pk).exists())
