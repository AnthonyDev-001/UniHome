import os
from uuid import uuid4

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.utils.deconstruct import deconstructible


@deconstructible
class PrivateStorage(FileSystemStorage):
    def __init__(self):
        super().__init__(file_permissions_mode=0o600, directory_permissions_mode=0o700)

    @property
    def base_location(self):
        return settings.PRIVATE_UPLOAD_ROOT

    @property
    def location(self):
        return os.path.abspath(self.base_location)

    def url(self, name):
        raise ValueError('Private files have no public storage URL.')


def private_path(instance, filename):
    # Validators supply normalized extensions; never retain user filenames/paths.
    extension = filename.rsplit('.', 1)[-1].lower()
    return f'{instance._meta.app_label}/{uuid4().hex}.{extension}'


private_storage = PrivateStorage()
