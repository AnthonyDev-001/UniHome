from django import forms
from django.contrib import admin, messages
from django.contrib.admin.helpers import ActionForm
from rest_framework.exceptions import APIException

from common.permissions import can_review


class ReviewActionForm(ActionForm):
    reason = forms.CharField(max_length=1000, required=True, label='Review reason')
    expires_at = forms.DateTimeField(required=False, label='Approval expires (optional, UTC)')


class ListingActionForm(ReviewActionForm):
    expected_revision = forms.IntegerField(min_value=1, label='Exact listing revision reviewed')


class ReadOnlyAdmin(admin.ModelAdmin):
    def get_readonly_fields(self, request, obj=None):
        return [f.name for f in self.model._meta.fields] + [f.name for f in self.model._meta.many_to_many]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class ReviewAdmin(ReadOnlyAdmin):
    action_form = ReviewActionForm
    actions = ['approve', 'reject', 'suspend', 'reopen']

    def has_view_permission(self, request, obj=None):
        return can_review(request.user, self.review_permission) or super().has_view_permission(request, obj)

    def get_actions(self, request):
        return super().get_actions(request) if can_review(request.user, self.review_permission) else {}

    def decide(self, request, queryset, decision):
        # Validate the same form used by the admin action UI, not raw POST values.
        form = self.action_form(request.POST, auto_id=None)
        form.fields['action'].choices = self.get_action_choices(request)
        if not form.is_valid():
            self.message_user(request, 'A valid review reason and expiry are required.', messages.ERROR)
            return
        for obj in queryset:
            try:
                self.review_object(request.user, obj, decision, form.cleaned_data['reason'], form.cleaned_data['expires_at'], expected_revision=form.cleaned_data.get('expected_revision'))
            except APIException as exc:
                self.message_user(request, f'{obj.pk}: {exc.detail}', messages.ERROR)
            else:
                self.message_user(request, f'{obj.pk}: {decision}', messages.SUCCESS)

    @admin.action(description='Approve selected records')
    def approve(self, request, queryset):
        self.decide(request, queryset, 'APPROVED')

    @admin.action(description='Reject selected records')
    def reject(self, request, queryset):
        self.decide(request, queryset, 'REJECTED')

    @admin.action(description='Suspend selected records')
    def suspend(self, request, queryset):
        self.decide(request, queryset, 'SUSPENDED')

    @admin.action(description='Reopen suspended/expired records for fresh review')
    def reopen(self, request, queryset):
        self.decide(request, queryset, 'REOPEN')
