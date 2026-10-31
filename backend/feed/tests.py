from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient
from .models import Post


class PostSecurityTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.owner = User.objects.create_user('owner')
        self.other = User.objects.create_user('other')
        self.post = Post.objects.create(author=self.owner, content='Original')
        self.url = f'/api/posts/{self.post.pk}/'

    def test_public_reads_and_anonymous_write_denial(self):
        self.assertEqual(self.client.get(self.url).status_code, 200)
        self.assertEqual(self.client.patch(self.url, {'content': 'bad'}).status_code, 401)
        self.assertEqual(self.client.post('/api/posts/', {'content': 'bad'}).status_code, 401)

    def test_cross_account_writes_are_denied(self):
        self.client.force_authenticate(self.other)
        for method in ['patch', 'put', 'delete']:
            with self.subTest(method=method):
                self.assertEqual(getattr(self.client, method)(self.url, {'content': 'bad'}).status_code, 403)
        self.post.refresh_from_db()
        self.assertEqual(self.post.content, 'Original')

    def test_author_can_edit_and_staff_can_moderate(self):
        self.client.force_authenticate(self.owner)
        self.assertEqual(self.client.patch(self.url, {'content': 'updated'}).status_code, 200)
        self.other.is_staff = True
        self.other.save()
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.delete(self.url).status_code, 204)

    def test_product_requires_positive_price_and_partial_update_preserves_invariant(self):
        self.client.force_authenticate(self.owner)
        for price in [None, '0.00', '-1.00']:
            with self.subTest(price=price):
                self.assertEqual(self.client.post('/api/posts/', {'content': 'item', 'is_product': True, 'price': price}, format='json').status_code, 400)
        self.assertEqual(self.client.patch(self.url, {'is_product': True}, format='json').status_code, 400)
        self.assertEqual(self.client.patch(self.url, {'is_product': True, 'price': '10.00'}, format='json').status_code, 200)
        self.assertEqual(self.client.patch(self.url, {'price': None}, format='json').status_code, 400)
