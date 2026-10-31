from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework import status
from feed.models import Post
from .models import Cart

class MarketplaceTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='testuser', password='testpassword')
        self.client.force_authenticate(user=self.user)
        self.product = Post.objects.create(author=self.user, content='Test Product', is_product=True, price=10.00)
        self.cart = Cart.objects.get(user=self.user)

    def test_add_item_to_cart(self):
        url = f'/api/marketplace/cart/{self.cart.id}/add_item/'
        data = {'product_id': self.product.id, 'quantity': 2}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.cart.items.count(), 1)
        self.assertEqual(self.cart.items.first().quantity, 2)

    def test_checkout(self):
        self.cart.items.create(product=self.product, quantity=1)
        url = '/api/marketplace/checkout/'
        response = self.client.post(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(self.cart.items.count(), 0)

    def test_invalid_input_leaves_no_cart_item(self):
        for quantity in [0, -1, 'abc', None, 1.5, 1000]:
            with self.subTest(quantity=quantity):
                response = self.client.post(f'/api/marketplace/cart/{self.cart.pk}/add_item/', {'product_id': self.product.pk, 'quantity': quantity}, format='json')
                self.assertEqual(response.status_code, 400)
                self.assertFalse(self.cart.items.exists())

    def test_quantity_accumulation_and_limit(self):
        url = f'/api/marketplace/cart/{self.cart.pk}/add_item/'
        self.assertEqual(self.client.post(url, {'product_id': self.product.pk, 'quantity': 998}).status_code, 200)
        self.assertEqual(self.client.post(url, {'product_id': self.product.pk, 'quantity': 2}).status_code, 400)
        self.assertEqual(self.cart.items.get().quantity, 998)
        self.assertEqual(self.client.post(url, {'product_id': self.product.pk}).status_code, 200)
        self.assertEqual(self.cart.items.get().quantity, 999)

    def test_cart_ownership(self):
        other = User.objects.create_user('other')
        for action in ['', 'add_item/', 'remove_item/']:
            url = f'/api/marketplace/cart/{other.cart.pk}/' + action
            response = self.client.post(url, {}) if action else self.client.get(url)
            self.assertEqual(response.status_code, 404)

    def test_checkout_rolls_back_order_and_preserves_cart(self):
        from unittest.mock import patch
        from .models import Order, OrderItem
        self.cart.items.create(product=self.product, quantity=2)
        with patch('marketplace.views.OrderItem.objects.create', side_effect=RuntimeError('injected')):
            with self.assertRaises(RuntimeError):
                self.client.post('/api/marketplace/checkout/')
        self.assertFalse(Order.objects.exists())
        self.assertFalse(OrderItem.objects.exists())
        self.assertEqual(self.cart.items.get().quantity, 2)

    def test_checkout_snapshot_and_idempotent_retry(self):
        from decimal import Decimal
        from .models import Order
        from django.db.models.deletion import ProtectedError
        self.cart.items.create(product=self.product, quantity=1)
        response = self.client.post('/api/marketplace/checkout/', HTTP_IDEMPOTENCY_KEY='checkout-1')
        self.assertEqual(response.status_code, 201)
        self.assertFalse(response.data['paid'])
        order = Order.objects.get()
        self.assertEqual(order.subtotal, Decimal('10.00'))
        self.assertEqual(order.fee_amount, Decimal('1.20'))
        self.assertEqual(order.total_price, Decimal('11.20'))
        retry = self.client.post('/api/marketplace/checkout/', HTTP_IDEMPOTENCY_KEY='checkout-1')
        self.assertEqual(retry.status_code, 200)
        self.assertEqual(retry.data['order_id'], order.pk)
        self.assertEqual(Order.objects.count(), 1)
        self.product.content = 'changed'
        self.product.save()
        self.product.delete()
        line = order.items.get()
        self.assertIsNone(line.product_id)
        self.assertEqual(line.product_description, 'Test Product')
        self.assertEqual(line.price, Decimal('10.00'))
        with self.assertRaises(ProtectedError):
            self.user.delete()

    def test_missing_cart_and_empty_checkout(self):
        self.assertEqual(self.client.post('/api/marketplace/checkout/').status_code, 400)
        self.cart.delete()
        self.assertEqual(self.client.post('/api/marketplace/checkout/').status_code, 400)

    def test_removed_or_unpriced_product_not_checkout_eligible(self):
        self.cart.items.create(product=self.product, quantity=1)
        self.product.is_product = False
        self.product.price = None
        self.product.save()
        self.assertEqual(self.client.post('/api/marketplace/checkout/').status_code, 400)
        self.assertTrue(self.cart.items.exists())
