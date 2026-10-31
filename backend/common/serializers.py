from rest_framework import serializers


class StrictModelSerializer(serializers.ModelSerializer):
    def to_internal_value(self, data):
        forbidden = set(data) - {name for name, field in self.fields.items() if not field.read_only}
        if forbidden:
            raise serializers.ValidationError({name: 'Unknown or read-only field.' for name in sorted(forbidden)})
        return super().to_internal_value(data)


class ReviewInput(serializers.Serializer):
    decision = serializers.ChoiceField(choices=['APPROVED', 'REJECTED', 'SUSPENDED', 'REOPEN'])
    reason = serializers.CharField(max_length=1000)
    expires_at = serializers.DateTimeField(required=False, allow_null=True)


class ListingReviewInput(ReviewInput):
    expected_revision = serializers.IntegerField(min_value=1)


class MediaReviewInput(serializers.Serializer):
    decision = serializers.ChoiceField(choices=['APPROVED', 'REJECTED'])
    reason = serializers.CharField(max_length=1000)
