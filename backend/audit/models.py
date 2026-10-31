import uuid
from django.conf import settings
from django.db import models


class AuditEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    action = models.CharField(max_length=80)
    target_type = models.CharField(max_length=80)
    target_id = models.CharField(max_length=64)
    reason = models.CharField(max_length=1000, blank=True)
    metadata = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        default_permissions = ('view',)

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError('Audit events are append-only.')
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError('Audit events cannot be deleted through the application.')


def record(actor, action, target, reason='', **metadata):
    return AuditEvent.objects.create(actor=actor, action=action,
        target_type=target._meta.label_lower, target_id=str(target.pk), reason=reason, metadata=metadata)
