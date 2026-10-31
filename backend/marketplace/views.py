from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.db import transaction
from rest_framework import mixins, permissions, serializers, status, views, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from feed.models import Post
from .models import Cart, CartItem, Order, OrderItem
from .serializers import CartSerializer


class AddItemInput(serializers.Serializer):
    product_id = serializers.IntegerField(min_value=1)
    quantity = serializers.IntegerField(min_value=1, max_value=999, default=1)


class RemoveItemInput(serializers.Serializer):
    item_id = serializers.IntegerField(min_value=1)


def order_response(order, code):
    return Response({
        'success': 'Unpaid order created. No payment has been collected.',
        'order_id': order.pk, 'paid': False, 'currency': order.currency,
        'subtotal': str(order.subtotal), 'fee_rate': str(order.fee_rate),
        'fee_amount': str(order.fee_amount), 'total_price': str(order.total_price),
    }, status=code)


class CartViewSet(mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = Cart.objects.all()
    serializer_class = CartSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return self.queryset.filter(user=self.request.user)

    @action(detail=True, methods=['post'])
    @transaction.atomic
    def add_item(self, request, pk=None):
        cart = self.get_object()
        data = AddItemInput(data=request.data)
        data.is_valid(raise_exception=True)
        cart = Cart.objects.select_for_update().get(pk=cart.pk)
        product = Post.objects.select_for_update().filter(pk=data.validated_data['product_id'], is_product=True).first()
        if product is None:
            return Response({'error': 'Product not found'}, status=404)
        if product.price is None or product.price <= 0:
            raise ValidationError({'product_id': 'Product has no valid price.'})
        item = CartItem.objects.filter(cart=cart, product=product).first()
        quantity = data.validated_data['quantity'] + (item.quantity if item else 0)
        if quantity > 999:
            raise ValidationError({'quantity': 'Cart quantity cannot exceed 999.'})
        if item:
            item.quantity = quantity
            item.save(update_fields=['quantity'])
        else:
            CartItem.objects.create(cart=cart, product=product, quantity=quantity)
        return Response(CartSerializer(cart).data)

    @action(detail=True, methods=['post'])
    @transaction.atomic
    def remove_item(self, request, pk=None):
        cart = self.get_object()
        data = RemoveItemInput(data=request.data)
        data.is_valid(raise_exception=True)
        Cart.objects.select_for_update().get(pk=cart.pk)
        deleted, _ = CartItem.objects.filter(pk=data.validated_data['item_id'], cart=cart).delete()
        if not deleted:
            return Response({'error': 'Item not found in cart'}, status=404)
        return Response(CartSerializer(cart).data)


class CheckoutView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        # All supported cart mutations lock the same row. PostgreSQL serializes
        # concurrent checkout/add/remove; SQLite is a single-user development option.
        cart = Cart.objects.select_for_update().filter(user=request.user).first()
        if cart is None:
            return Response({'error': 'Your cart is empty'}, status=400)
        key = request.headers.get('Idempotency-Key')
        if key is not None and (not key.strip() or len(key) > 128):
            raise ValidationError({'Idempotency-Key': 'Use 1–128 nonblank characters.'})
        if key:
            existing = Order.objects.filter(user=request.user, idempotency_key=key).first()
            if existing:
                return order_response(existing, status.HTTP_200_OK)
        items = list(cart.items.order_by('pk'))
        if not items:
            return Response({'error': 'Your cart is empty'}, status=400)
        products = {p.pk: p for p in Post.objects.select_for_update().filter(pk__in=[i.product_id for i in items]).order_by('pk')}
        for item in items:
            p = products.get(item.product_id)
            if p is None or not p.is_product or p.price is None or p.price <= 0 or not 1 <= item.quantity <= 999:
                raise ValidationError({'cart': 'Cart contains an unavailable or invalid product.'})
        subtotal = sum((products[i.product_id].price * i.quantity for i in items), Decimal('0.00'))
        fee = (subtotal * settings.MARKETPLACE_FEE_RATE).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        total = subtotal + fee
        if total > Decimal('99999999.99'):
            raise ValidationError({'cart': 'Order total exceeds the supported limit.'})
        order = Order.objects.create(user=request.user, subtotal=subtotal, fee_amount=fee,
                                     fee_rate=settings.MARKETPLACE_FEE_RATE, total_price=total,
                                     idempotency_key=key)
        for item in items:
            product = products[item.product_id]
            OrderItem.objects.create(order=order, product=product, quantity=item.quantity,
                                     price=product.price, product_description=product.content)
        cart.items.all().delete()
        return order_response(order, status.HTTP_201_CREATED)
