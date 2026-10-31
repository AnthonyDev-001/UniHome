from django.contrib import admin
from .models import Order, OrderItem


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'total_price', 'currency', 'paid', 'created_at')

    def get_readonly_fields(self, request, obj=None):
        return [f.name for f in self.model._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(OrderItem)
class OrderItemAdmin(OrderAdmin):
    list_display = ('id', 'order', 'product_description', 'quantity', 'price')

# Cart modifications must go through the locked API services.
