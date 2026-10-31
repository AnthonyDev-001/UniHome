import io
import json
import shutil
import subprocess
import tempfile
from datetime import timedelta
from pathlib import Path
from unittest import skipUnless

from django.contrib.auth.models import Permission, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from PIL import Image
from rest_framework.test import APIClient

from audit.models import AuditEvent
from verification.models import PropertyAuthority, ReviewStatus, VerificationCase
from .models import ListingRevision, Property, PropertyMedia, Unit


def image_file():
    output = io.BytesIO()
    image = Image.new('RGB', (32, 32), 'blue')
    exif = image.getexif()
    exif[270] = 'private metadata'
    image.save(output, format='JPEG', exif=exif)
    return SimpleUploadedFile('untrusted-name.jpg', output.getvalue(), content_type='image/jpeg')


def evidence_file():
    return SimpleUploadedFile('sensitive-document.pdf', b'%PDF-1.4\nSynthetic test evidence only\n%%EOF', content_type='application/pdf')


class RentalAPITests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.storage = tempfile.TemporaryDirectory()
        cls.settings_override = override_settings(PRIVATE_UPLOAD_ROOT=Path(cls.storage.name))
        cls.settings_override.enable()
        cls.video_bytes = None
        if shutil.which('ffmpeg') and shutil.which('ffprobe'):
            path = Path(cls.storage.name) / 'test.mp4'
            subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=c=blue:s=64x64:r=10', '-t', '1', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-metadata', 'title=Private container title', str(path)], check=True, capture_output=True)
            cls.video_bytes = path.read_bytes()

    @classmethod
    def tearDownClass(cls):
        cls.settings_override.disable()
        cls.storage.cleanup()
        super().tearDownClass()

    def setUp(self):
        self.owner = User.objects.create_user('owner', password='owner-password-729!')
        self.other = User.objects.create_user('other')
        self.reviewer = User.objects.create_user('reviewer', is_staff=True)
        self.reviewer.user_permissions.set(Permission.objects.filter(codename__in=['review_verification', 'review_authority', 'review_listing', 'review_media', 'view_auditevent']))
        self.client = APIClient()
        self.client.force_authenticate(self.owner)
        self.staff = APIClient()
        self.staff.force_authenticate(self.reviewer)
        self.public = APIClient()
        self.property = self.create_property()

    def create_property(self):
        response = self.client.post('/api/v1/management/properties/', {
            'title': 'Campus home', 'description': 'Synthetic test property', 'category': 'STUDENT',
            'state': 'Enugu', 'city': 'Nsukka', 'area': 'Campus area', 'campus': 'Example university',
            'private_address': 'Private exact test address', 'rules': 'No smoking',
        }, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        return Property.objects.get(pk=response.data['id'])

    def identity(self, approve=True, applicant=None):
        client = self.client
        applicant = applicant or self.owner
        response = client.post('/api/v1/verification/cases/', {'role': 'AGENT'})
        self.assertEqual(response.status_code, 201, response.data)
        case = VerificationCase.objects.get(pk=response.data['id'])
        response = client.post('/api/v1/verification/documents/', {'case': str(case.pk), 'file': evidence_file()}, format='multipart')
        self.assertEqual(response.status_code, 201, response.data)
        self.document_id = response.data['id']
        self.assertEqual(client.post(f'/api/v1/verification/cases/{case.pk}/submit/').status_code, 200)
        if approve:
            response = self.staff.post(f'/api/v1/verification/cases/{case.pk}/review/', {'decision': 'APPROVED', 'reason': 'Synthetic identity evidence reviewed'})
            self.assertEqual(response.status_code, 200, response.data)
        case.refresh_from_db()
        return case

    def authority(self):
        case = self.identity()
        response = self.client.post('/api/v1/verification/authorities/', {'property': str(self.property.pk), 'verification': str(case.pk)})
        self.assertEqual(response.status_code, 201, response.data)
        authority = PropertyAuthority.objects.get(pk=response.data['id'])
        response = self.client.post('/api/v1/verification/documents/', {'authority': str(authority.pk), 'file': evidence_file()}, format='multipart')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(self.client.post(f'/api/v1/verification/authorities/{authority.pk}/submit/').status_code, 200)
        response = self.staff.post(f'/api/v1/verification/authorities/{authority.pk}/review/', {'decision': 'APPROVED', 'reason': 'Synthetic property authority evidence reviewed'})
        self.assertEqual(response.status_code, 200, response.data)
        authority.refresh_from_db()
        return authority

    def unit(self, **overrides):
        data = {'property': str(self.property.pk), 'label': 'Room A', 'kind': 'ROOM', 'capacity': 1,
                'rent': '100000.00', 'billing_period': 'YEAR', 'available_from': str(timezone.now().date())}
        data.update(overrides)
        response = self.client.post('/api/v1/units/', data, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        return Unit.objects.get(pk=response.data['id'])

    def approved_media(self):
        if self.video_bytes is None:
            self.skipTest('ffmpeg and ffprobe required for real video validation')
        self.media_ids = []
        for kind, file in [('IMAGE', image_file()), ('VIDEO', SimpleUploadedFile('tour.mp4', self.video_bytes, content_type='video/mp4'))]:
            response = self.client.post('/api/v1/media/', {'property': str(self.property.pk), 'kind': kind, 'caption': 'Synthetic tour', 'file': file}, format='multipart')
            self.assertEqual(response.status_code, 201, response.data)
            media_id = response.data['id']
            self.media_ids.append(media_id)
            self.assertEqual(self.public.get(f'/api/v1/media/{media_id}/file/').status_code, 404)
            response = self.staff.post(f'/api/v1/media/{media_id}/review/', {'decision': 'APPROVED', 'reason': 'Synthetic media reviewed'})
            self.assertEqual(response.status_code, 200, response.data)
            if kind == 'VIDEO':
                media = PropertyMedia.objects.get(pk=media_id)
                probe = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format_tags', '-of', 'json', media.file.path], check=True, capture_output=True)
                self.assertNotIn('Private container title', probe.stdout.decode())

    def publish(self, via_admin=False):
        self.authority()
        unit = self.unit()
        self.approved_media()
        response = self.client.post(f'/api/v1/management/properties/{self.property.pk}/submit/')
        self.assertEqual(response.status_code, 200, response.data)
        revision = response.data['revision']
        if via_admin:
            self.staff.force_login(self.reviewer)
            response = self.staff.post('/admin/properties/property/', {'action': 'approve', '_selected_action': str(self.property.pk), 'reason': 'Reviewed full listing revision', 'expected_revision': revision})
            self.assertEqual(response.status_code, 302)
            self.property.refresh_from_db()
            self.assertEqual(self.property.status, Property.Status.ACTIVE)
        else:
            response = self.staff.post(f'/api/v1/management/properties/{self.property.pk}/review/', {
                'decision': 'APPROVED', 'reason': 'Reviewed full listing revision', 'expected_revision': revision})
            self.assertEqual(response.status_code, 200, response.data)
        self.property.refresh_from_db()
        return unit

    def test_unverified_cannot_publish_and_status_cannot_be_forged(self):
        self.assertEqual(self.client.post(f'/api/v1/management/properties/{self.property.pk}/submit/').status_code, 400)
        self.assertEqual(self.client.patch(f'/api/v1/management/properties/{self.property.pk}/', {'status': 'ACTIVE'}, format='json').status_code, 400)
        self.assertEqual(self.public.get(f'/api/v1/properties/{self.property.pk}/').status_code, 404)
        self.property.refresh_from_db()
        self.assertEqual(self.property.status, Property.Status.DRAFT)

    def test_cross_account_mutations_and_parent_reassignment_are_denied(self):
        unit = self.unit()
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.patch(f'/api/v1/management/properties/{self.property.pk}/', {'title': 'Stolen'}, format='json').status_code, 404)
        self.assertEqual(self.client.patch(f'/api/v1/units/{unit.pk}/', {'rent': '1.00'}, format='json').status_code, 404)
        self.assertEqual(self.client.post('/api/v1/units/', {'property': str(self.property.pk), 'label': 'B', 'kind': 'ROOM', 'rent': '100', 'billing_period': 'YEAR', 'available_from': '2027-01-01'}).status_code, 400)
        self.client.force_authenticate(self.owner)
        second = self.create_property()
        self.assertEqual(self.client.patch(f'/api/v1/units/{unit.pk}/', {'property': str(second.pk)}, format='json').status_code, 400)

    def test_identity_evidence_is_required_and_cannot_be_modified_after_submission(self):
        response = self.client.post('/api/v1/verification/cases/', {'role': 'LANDLORD'})
        case_id = response.data['id']
        self.assertEqual(self.client.post(f'/api/v1/verification/cases/{case_id}/submit/').status_code, 400)
        case = self.identity(approve=False)
        self.assertEqual(self.client.post('/api/v1/verification/documents/', {'case': str(case.pk), 'file': evidence_file()}, format='multipart').status_code, 400)
        self.assertEqual(self.client.patch(f'/api/v1/verification/cases/{case.pk}/', {'status': 'APPROVED'}).status_code, 405)

    def test_private_document_download_permissions_and_storage(self):
        self.identity()
        url = f'/api/v1/verification/documents/{self.document_id}/file/'
        self.assertEqual(self.public.get(url).status_code, 401)
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.client.force_authenticate(self.owner)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn('attachment', response['Content-Disposition'])
        self.assertEqual(response['Cache-Control'], 'private, no-store')
        self.assertTrue(b''.join(response.streaming_content))
        staff_response = self.staff.get(url)
        self.assertEqual(staff_response.status_code, 200)
        self.assertTrue(b''.join(staff_response.streaming_content))
        from verification.models import EvidenceDocument
        document = EvidenceDocument.objects.get(pk=self.document_id)
        self.assertNotIn('sensitive-document', document.file.name)
        with self.assertRaises(ValueError):
            _ = document.file.url

    def test_reviewer_permission_and_self_approval(self):
        self.client.force_authenticate(self.reviewer)
        case = self.identity(approve=False, applicant=self.reviewer)
        response = self.staff.post(f'/api/v1/verification/cases/{case.pk}/review/', {'decision': 'APPROVED', 'reason': 'Self approval attempted'})
        self.assertEqual(response.status_code, 403)
        ordinary_staff = User.objects.create_user('staff-without-permission', is_staff=True)
        self.client.force_authenticate(ordinary_staff)
        self.assertEqual(self.client.post(f'/api/v1/verification/cases/{case.pk}/review/', {'decision': 'APPROVED', 'reason': 'Not authorized'}).status_code, 403)

    def test_publication_hides_sensitive_data_and_rechecks_revocation(self):
        unit = self.publish()
        self.assertTrue(self.public.get(f'/api/v1/properties/{self.property.pk}/').data['verification']['listing_authority_reviewed'])
        response = self.public.get('/api/v1/properties/')
        self.assertEqual(response.data['count'], 1)
        serialized = json.dumps(response.data)
        for private_value in ['private_address', 'Private exact test address', 'review_note', 'private_uploads', 'reviewed_by']:
            self.assertNotIn(private_value, serialized)
        for media_id in self.media_ids:
            response = self.public.get(f'/api/v1/media/{media_id}/file/')
            self.assertEqual(response.status_code, 200)
            self.assertTrue(b''.join(response.streaming_content))
        authority = PropertyAuthority.objects.get(property=self.property)
        response = self.staff.post(f'/api/v1/verification/authorities/{authority.pk}/review/', {'decision': 'SUSPENDED', 'reason': 'Authority withdrawn'})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(self.public.get(f'/api/v1/properties/{self.property.pk}/').status_code, 404)
        self.assertEqual(self.public.get(f'/api/v1/media/{self.media_ids[0]}/file/').status_code, 404)
        self.assertTrue(AuditEvent.objects.filter(action='listing.suspended', target_id=str(self.property.pk)).exists())

    def test_expired_identity_hides_previously_approved_listing(self):
        self.publish()
        VerificationCase.objects.filter(applicant=self.owner).update(expires_at=timezone.now()-timedelta(seconds=1))
        self.assertEqual(self.public.get('/api/v1/properties/').data['count'], 0)

    def test_content_changes_withdraw_and_suspensions_cannot_be_bypassed(self):
        unit = self.publish()
        before = self.property.revision
        response = self.client.patch(f'/api/v1/units/{unit.pk}/', {'rent': '200000.00'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.property.refresh_from_db()
        self.assertEqual(self.property.status, Property.Status.DRAFT)
        self.assertGreater(self.property.revision, before)
        self.assertEqual(self.public.get('/api/v1/properties/').data['count'], 0)
        self.staff.post(f'/api/v1/management/properties/{self.property.pk}/review/', {'decision': 'SUSPENDED', 'reason': 'Investigation', 'expected_revision': self.property.revision})
        self.client.patch(f'/api/v1/management/properties/{self.property.pk}/', {'title': 'Changed'}, format='json')
        self.property.refresh_from_db()
        self.assertEqual(self.property.status, Property.Status.SUSPENDED)
        self.assertEqual(self.client.post(f'/api/v1/management/properties/{self.property.pk}/submit/').status_code, 400)

    def test_stale_revision_cannot_be_approved(self):
        self.authority()
        self.unit()
        self.approved_media()
        response = self.client.post(f'/api/v1/management/properties/{self.property.pk}/submit/')
        revision = response.data['revision']
        self.client.patch(f'/api/v1/management/properties/{self.property.pk}/', {'title': 'New title'}, format='json')
        response = self.staff.post(f'/api/v1/management/properties/{self.property.pk}/review/', {'decision': 'APPROVED', 'reason': 'Old review', 'expected_revision': revision})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(ListingRevision.objects.get(property=self.property).snapshot['title'], 'Campus home')

    def test_availability_blocks_reject_overlap_and_inactive_space_is_unavailable(self):
        from .services import unit_available
        unit = self.unit()
        start = timezone.now().date()
        end = start + timedelta(days=3)
        url = f'/api/v1/units/{unit.pk}/blocks/'
        response = self.client.post(url, {'starts_on': str(start), 'ends_on': str(end), 'reason': 'Maintenance'})
        self.assertEqual(response.status_code, 201, response.data)
        block_id = response.data['id']
        self.assertFalse(unit_available(unit, start, end))
        self.assertEqual(self.client.post(url, {'starts_on': str(start+timedelta(days=1)), 'ends_on': str(end+timedelta(days=1)), 'reason': 'Overlap'}).status_code, 400)
        self.assertEqual(self.client.post(url, {'starts_on': str(end), 'ends_on': str(end+timedelta(days=1)), 'reason': 'Adjacent'}).status_code, 201)
        self.assertEqual(self.client.post(f'/api/v1/units/{unit.pk}/cancel-block/', {'block_id': block_id}).status_code, 200)
        self.assertTrue(unit_available(unit, start, end))
        unit.status = Unit.Status.UNAVAILABLE
        self.assertFalse(unit_available(unit, start, end))

    def test_price_breakdown_and_search_period_validation(self):
        unit = self.publish()
        response = self.client.post('/api/v1/charges/', {'unit': str(unit.pk), 'kind': 'DEPOSIT', 'label': 'Refundable deposit', 'amount': '20000.00', 'refundable': True, 'recurring': False}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(self.client.post(f'/api/v1/management/properties/{self.property.pk}/submit/').status_code, 200)
        self.property.refresh_from_db()
        self.assertEqual(self.staff.post(f'/api/v1/management/properties/{self.property.pk}/review/', {'decision': 'APPROVED', 'reason': 'Reviewed disclosed fees', 'expected_revision': self.property.revision}).status_code, 200)
        detail = self.public.get(f'/api/v1/properties/{self.property.pk}/').data
        self.assertEqual(detail['units'][0]['total_first_period'], '120000.00')
        self.assertEqual(self.public.get('/api/v1/properties/?max_rent=120000').status_code, 400)
        response = self.public.get('/api/v1/properties/?billing_period=YEAR&max_rent=120000&category=STUDENT&city=Nsukka')
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(self.public.get('/api/v1/properties/?billing_period=MONTH&max_rent=120000').data['count'], 0)

    def test_upload_content_validation_and_metadata_removal(self):
        response = self.client.post('/api/v1/media/', {'property': str(self.property.pk), 'kind': 'VIDEO', 'caption': 'Fake', 'file': SimpleUploadedFile('fake.mp4', b'not a movie', content_type='video/mp4')}, format='multipart')
        self.assertEqual(response.status_code, 400, response.data)
        response = self.client.post('/api/v1/media/', {'property': str(self.property.pk), 'kind': 'IMAGE', 'caption': 'Photo', 'file': image_file()}, format='multipart')
        self.assertEqual(response.status_code, 201, response.data)
        media = PropertyMedia.objects.get(pk=response.data['id'])
        with media.file.open('rb') as f:
            self.assertFalse(Image.open(f).getexif())
        self.assertEqual(media.status, PropertyMedia.Status.PENDING)
        self.assertEqual(self.public.get(f'/api/v1/media/{media.pk}/file/').status_code, 404)

    def test_report_and_audit_access(self):
        self.publish()
        response = self.client.post(f'/api/v1/properties/{self.property.pk}/report/', {'reason': 'MISLEADING', 'details': 'Synthetic test report'})
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(self.client.get('/api/v1/audit/').status_code, 403)
        self.assertEqual(self.staff.get('/api/v1/audit/').status_code, 200)
        event = AuditEvent.objects.first()
        event.reason = 'rewrite attempt'
        with self.assertRaises(ValueError):
            event.save()
        with self.assertRaises(ValueError):
            event.delete()

    def test_suspension_cannot_be_lifted_via_withdrawal(self):
        self.staff.post(f'/api/v1/management/properties/{self.property.pk}/review/', {'decision': 'SUSPENDED', 'reason': 'Investigation', 'expected_revision': self.property.revision})
        self.assertEqual(self.client.post(f'/api/v1/management/properties/{self.property.pk}/withdraw/', {'status': 'UNAVAILABLE'}).status_code, 400)
        self.property.refresh_from_db()
        self.assertEqual(self.property.status, Property.Status.SUSPENDED)

    def test_no_mixed_room_and_bed_inventory_or_invalid_pricing(self):
        self.unit()
        data = {'property': str(self.property.pk), 'label': 'Bed A', 'kind': 'BED', 'rent': '10000', 'billing_period': 'MONTH', 'available_from': '2027-01-01'}
        self.assertEqual(self.client.post('/api/v1/units/', data).status_code, 400)
        for rent in ['0', '-1']:
            data.update(label='Room B', kind='ROOM', rent=rent)
            self.assertEqual(self.client.post('/api/v1/units/', data).status_code, 400)

    def test_media_rejection_suspends_live_listing_and_hides_files(self):
        self.publish()
        response = self.staff.post(f'/api/v1/media/{self.media_ids[0]}/review/', {'decision': 'REJECTED', 'reason': 'Misleading media identified'})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(self.public.get('/api/v1/properties/').data['count'], 0)
        self.assertEqual(self.public.get(f'/api/v1/media/{self.media_ids[0]}/file/').status_code, 404)

    def test_search_availability_respects_blocks(self):
        unit = self.publish()
        day = timezone.now().date()
        # Use a service/API mutation, then re-review the resulting revision.
        self.client.post(f'/api/v1/units/{unit.pk}/blocks/', {'starts_on': str(day), 'ends_on': str(day+timedelta(days=2)), 'reason': 'Maintenance'})
        self.assertEqual(self.client.post(f'/api/v1/management/properties/{self.property.pk}/submit/').status_code, 200)
        self.property.refresh_from_db()
        self.assertEqual(self.staff.post(f'/api/v1/management/properties/{self.property.pk}/review/', {'decision': 'APPROVED', 'reason': 'Availability disclosed', 'expected_revision': self.property.revision}).status_code, 200)
        self.assertEqual(self.public.get(f'/api/v1/properties/?available_on={day}').data['count'], 0)
        self.assertEqual(self.public.get(f'/api/v1/properties/?available_on={day+timedelta(days=2)}').data['count'], 1)

    def test_report_resolution_is_restricted_and_audited(self):
        self.publish()
        self.client.force_authenticate(self.other)
        response = self.client.post(f'/api/v1/properties/{self.property.pk}/report/', {'reason': 'OTHER', 'details': 'Synthetic report'})
        report_id = response.data['id']
        self.assertEqual(self.client.post(f'/api/v1/reports/{report_id}/resolve/', {'reason': 'Self resolve'}).status_code, 403)
        self.client.force_authenticate(self.owner)
        self.assertEqual(self.client.get(f'/api/v1/reports/{report_id}/').status_code, 404)
        self.assertEqual(self.staff.post(f'/api/v1/reports/{report_id}/resolve/', {'reason': 'Reviewed supporting information'}).status_code, 200)
        self.assertTrue(AuditEvent.objects.filter(action='report.resolved', target_id=str(report_id)).exists())

    def test_admin_review_requires_exact_revision_and_uses_transition_service(self):
        from django.contrib.auth.models import Group
        from django.core.management import call_command
        call_command('bootstrap_rental_roles', verbosity=0)
        call_command('bootstrap_rental_roles', verbosity=0)
        self.reviewer.groups.add(*Group.objects.filter(name__in=['UniHome listing moderators', 'UniHome media reviewers', 'UniHome identity reviewers', 'UniHome authority reviewers']))
        self.publish(via_admin=True)
        self.staff.force_login(self.reviewer)
        response = self.staff.post('/admin/properties/property/', {
            'action': 'suspend', '_selected_action': str(self.property.pk), 'reason': 'Admin moderation',
            'expected_revision': self.property.revision - 1,
        })
        self.assertEqual(response.status_code, 302)
        self.property.refresh_from_db()
        self.assertEqual(self.property.status, Property.Status.ACTIVE)
        response = self.staff.post('/admin/properties/property/', {
            'action': 'suspend', '_selected_action': str(self.property.pk), 'reason': 'Admin moderation',
            'expected_revision': self.property.revision,
        })
        self.assertEqual(response.status_code, 302)
        self.property.refresh_from_db()
        self.assertEqual(self.property.status, Property.Status.SUSPENDED)
        # Even authorized reviewers cannot bypass services through a generic admin save.
        forged = self.staff.post(f'/admin/properties/property/{self.property.pk}/change/', {'status': 'ACTIVE', '_save': 'Save'})
        self.assertEqual(forged.status_code, 403)
        self.property.refresh_from_db()
        self.assertEqual(self.property.status, Property.Status.SUSPENDED)
        from verification.models import EvidenceDocument
        document = EvidenceDocument.objects.first()
        response = self.staff.get(f'/admin/verification/evidencedocument/{document.pk}/change/')
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, document.file.name)
        self.assertContains(response, 'Download as attachment')

    def test_upload_limits_and_missing_video_validator_fail_closed(self):
        from common.uploads import validate_video
        from rest_framework.exceptions import ValidationError
        large = SimpleUploadedFile('large.mp4', b'0' * (50*1024*1024 + 1))
        with self.assertRaises(ValidationError):
            validate_video(large)
        with override_settings(FFPROBE_BINARY='/nonexistent/ffprobe'):
            with self.assertRaises(ValidationError):
                validate_video(SimpleUploadedFile('small.mp4', b'not video'))
