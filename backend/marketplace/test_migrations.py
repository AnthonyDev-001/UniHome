from decimal import Decimal

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class LegacyMigrationTests(TransactionTestCase):
    old = [('feed', '0001_initial'), ('marketplace', '0001_initial')]

    def setUp(self):
        executor = MigrationExecutor(connection)
        self.leaves = executor.loader.graph.leaf_nodes()
        executor.migrate(self.old)
        self.apps = executor.loader.project_state(self.old).apps

    def tearDown(self):
        # Restore the schema even if an assertion fails.
        self.apps.get_model('marketplace', 'CartItem').objects.all().delete()
        self.apps.get_model('feed', 'Post').objects.filter(price__lte=0).delete()
        self.apps.get_model('feed', 'Post').objects.filter(is_product=True, price__isnull=True).delete()
        MigrationExecutor(connection).migrate(self.leaves)
        super().tearDown()

    def test_legacy_upgrade_preserves_totals_and_snapshots_existing_lines(self):
        user = self.apps.get_model('auth', 'User').objects.create(username='legacy')
        post = self.apps.get_model('feed', 'Post').objects.create(author_id=user.pk, content='Legacy item', is_product=True, price='10.00')
        order = self.apps.get_model('marketplace', 'Order').objects.create(user_id=user.pk, total_price='11.20')
        self.apps.get_model('marketplace', 'OrderItem').objects.create(order_id=order.pk, product_id=post.pk, quantity=1, price='10.00')
        MigrationExecutor(connection).migrate(self.leaves)
        from .models import Order
        upgraded = Order.objects.get(pk=order.pk)
        self.assertEqual(upgraded.total_price, Decimal('11.20'))
        self.assertEqual(upgraded.currency, '')
        self.assertIsNone(upgraded.subtotal)
        self.assertIsNone(upgraded.fee_amount)
        self.assertEqual(upgraded.items.get().product_description, 'Legacy item')

    def test_invalid_legacy_data_requires_explicit_repair(self):
        user = self.apps.get_model('auth', 'User').objects.create(username='invalid-legacy')
        post = self.apps.get_model('feed', 'Post').objects.create(author_id=user.pk, content='invalid', is_product=True)
        with self.assertRaisesRegex(RuntimeError, 'Invalid legacy product prices'):
            MigrationExecutor(connection).migrate(self.leaves)
        post.price = '10.00'
        post.save()
        cart = self.apps.get_model('marketplace', 'Cart').objects.create(user_id=user.pk)
        item = self.apps.get_model('marketplace', 'CartItem').objects.create(cart_id=cart.pk, product_id=post.pk, quantity=0)
        with self.assertRaisesRegex(RuntimeError, 'Invalid/duplicate legacy cart'):
            MigrationExecutor(connection).migrate(self.leaves)
        item.quantity = 1
        item.save()
        MigrationExecutor(connection).migrate(self.leaves)
