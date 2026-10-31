from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = 'Create additive rental review permission groups; never enroll users or grant staff status.'

    @transaction.atomic
    def handle(self, *args, **options):
        groups = {
            'UniHome identity reviewers': [('verification', c) for c in ['review_verification', 'view_verificationcase', 'view_evidencedocument']],
            'UniHome authority reviewers': [('verification', c) for c in ['review_authority', 'view_propertyauthority', 'view_evidencedocument']],
            'UniHome listing moderators': [('properties', c) for c in ['review_listing', 'view_property', 'view_unit', 'view_unitcharge', 'view_availabilityblock', 'view_propertymedia', 'view_listingrevision', 'view_listingreport']],
            'UniHome media reviewers': [('properties', c) for c in ['review_media', 'view_propertymedia']],
            'UniHome auditors': [('audit', 'view_auditevent')],
        }
        for name, permissions in groups.items():
            group, _ = Group.objects.get_or_create(name=name)
            for app, codename in permissions:
                group.permissions.add(Permission.objects.get(content_type__app_label=app, codename=codename))
            if options['verbosity']:
                self.stdout.write(f'Prepared {name}')
