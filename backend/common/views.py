from django.db import IntegrityError
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class RentalPagination(PageNumberPagination):
    page_size = 25
    max_page_size = 100


class ConflictResponseMixin:
    pagination_class = RentalPagination

    def handle_exception(self, exc):
        if isinstance(exc, IntegrityError):
            return Response({'detail': 'Conflicting change. Reload and retry.'}, status=409)
        return super().handle_exception(exc)
