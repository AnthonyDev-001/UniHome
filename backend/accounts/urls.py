from django.urls import path
from .views import RegisterView, LoginView, RefreshView, PasswordResetRequestView, PasswordResetConfirmView


urlpatterns = [
    path('password-reset/', PasswordResetRequestView.as_view(), name='password_reset'),
    path('password-reset/confirm/', PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('register/', RegisterView.as_view(), name='register'),
    path('token/', LoginView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', RefreshView.as_view(), name='token_refresh'),
]
