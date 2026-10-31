from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless

from django.contrib.auth.models import User
from django.db import close_old_connections, connection
from django.test import TransactionTestCase
from rest_framework.test import APIClient

from feed.models import Post
from .models import Order


@skipUnless(connection.vendor == 'postgresql', 'Row-locking contracts require PostgreSQL')
class CartConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.user = User.objects.create_user('concurrent')
        self.product = Post.objects.create(author=self.user, content='item', is_product=True, price='10.00')
        self.cart = self.user.cart

    def race(self, url, data=None, key=None):
        barrier = Barrier(2)
        def worker():
            close_old_connections()
            try:
                client = APIClient()
                client.force_authenticate(User.objects.get(pk=self.user.pk))
                barrier.wait(timeout=10)
                kwargs = {'HTTP_IDEMPOTENCY_KEY': key} if key else {}
                return client.post(url, data or {}, format='json', **kwargs).status_code
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(worker) for _ in range(2)]
            return sorted(f.result(timeout=30) for f in futures)

    def test_duplicate_checkout_without_key_creates_one_order(self):
        self.cart.items.create(product=self.product, quantity=1)
        self.assertEqual(self.race('/api/marketplace/checkout/'), [201, 400])
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(Order.objects.get().items.count(), 1)

    def test_duplicate_checkout_key_returns_same_order(self):
        self.cart.items.create(product=self.product, quantity=1)
        self.assertEqual(self.race('/api/marketplace/checkout/', key='concurrent-checkout'), [200, 201])
        self.assertEqual(Order.objects.count(), 1)

    def test_simultaneous_add_does_not_lose_quantity(self):
        self.assertEqual(self.race(f'/api/marketplace/cart/{self.cart.pk}/add_item/', {'product_id': self.product.pk, 'quantity': 1}), [200, 200])
        self.assertEqual(self.cart.items.count(), 1)
        self.assertEqual(self.cart.items.get().quantity, 2)
