from rest_framework import serializers
from .models import Post

class PostSerializer(serializers.ModelSerializer):
    class Meta:
        model = Post
        fields = ['id', 'author', 'content', 'image', 'is_product', 'price', 'category', 'date_posted']
        read_only_fields = ['author', 'date_posted']

    def validate(self, attrs):
        product = attrs.get('is_product', getattr(self.instance, 'is_product', False))
        price = attrs.get('price', getattr(self.instance, 'price', None))
        if price is not None and price <= 0:
            raise serializers.ValidationError({'price': 'Price must be positive.'})
        if product and price is None:
            raise serializers.ValidationError({'price': 'Products require a price.'})
        return attrs

    def validate_image(self, value):
        if value.size > 5 * 1024 * 1024:
            raise serializers.ValidationError('Image must be at most 5 MiB.')
        if value.image.format not in {'JPEG', 'PNG', 'WEBP'}:
            raise serializers.ValidationError('Use JPEG, PNG or WebP.')
        return value
