from rest_framework.permissions import BasePermission


def can_review(user, permission):
    return bool(user.is_authenticated and user.is_active and user.is_staff and user.has_perm(permission))


class ReviewPermission(BasePermission):
    def has_permission(self, request, view):
        return can_review(request.user, view.review_permission)
