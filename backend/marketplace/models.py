from django.db import models
from django.contrib.auth.models import User
from feed.models import Post

class Cart(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Cart for {self.user.username}"

class CartItem(models.Model):
    cart = models.ForeignKey(Cart, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Post, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['cart', 'product'], name='unique_cart_product'),
            models.CheckConstraint(condition=models.Q(quantity__gte=1) & models.Q(quantity__lte=999), name='cart_quantity_range'),
        ]

    def __str__(self):
        return f"{self.quantity} of {self.product.content} in cart for {self.cart.user.username}"

class Order(models.Model):
    user = models.ForeignKey(User, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    paid = models.BooleanField(default=False)
    currency = models.CharField(max_length=3, default='NGN')
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    fee_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    fee_rate = models.DecimalField(max_digits=5, decimal_places=4, null=True)
    idempotency_key = models.CharField(max_length=128, null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['user', 'idempotency_key'], name='unique_user_checkout_key')]


    def __str__(self):
        return f"Order {self.id} by {self.user.username}"

class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Post, null=True, blank=True, on_delete=models.SET_NULL)
    product_description = models.TextField(default='')
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.quantity} of {self.product_description}"
