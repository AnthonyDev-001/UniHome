from rest_framework import generics, permissions
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from django.contrib.auth.models import User
from .serializers import UserSerializer

class RegisterView(generics.CreateAPIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"
    queryset = User.objects.all()
    serializer_class = UserSerializer

class LoginView(TokenObtainPairView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'auth'

class RefreshView(TokenRefreshView):
    from .serializers import PasswordAwareRefreshSerializer
    serializer_class = PasswordAwareRefreshSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'auth'


class PasswordResetRequestView(generics.GenericAPIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'auth'

    def post(self, request):
        from django.conf import settings
        from django.contrib.auth.tokens import default_token_generator
        from django.core.mail import send_mail
        from django.utils.encoding import force_bytes
        from django.utils.http import urlsafe_base64_encode
        from rest_framework.response import Response
        from .serializers import ResetRequestSerializer

        if not settings.ACCOUNT_RESET_URL:
            return Response({'error': 'Account recovery is not configured.'}, status=503)
        data = ResetRequestSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        users = list(User.objects.filter(email__iexact=data.validated_data['email'], is_active=True)[:2])
        # Legacy email addresses are not unique. Never guess an account.
        if len(users) == 1 and users[0].has_usable_password():
            user = users[0]
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            send_mail('UniHome password reset',
                      f'Reset your password: {settings.ACCOUNT_RESET_URL}?uid={uid}&token={token}',
                      settings.DEFAULT_FROM_EMAIL, [user.email])
        return Response({'detail': 'If an eligible account exists, recovery instructions will be sent.'})


class PasswordResetConfirmView(generics.GenericAPIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'auth'

    def post(self, request):
        from django.contrib.auth.tokens import default_token_generator
        from django.contrib.auth.password_validation import validate_password
        from django.core.exceptions import ValidationError as DjangoValidationError
        from django.db import transaction
        from django.utils.http import urlsafe_base64_decode
        from rest_framework.exceptions import ValidationError
        from rest_framework.response import Response
        from .serializers import ResetConfirmSerializer

        data = ResetConfirmSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        with transaction.atomic():
            try:
                uid = urlsafe_base64_decode(data.validated_data['uid']).decode()
                user = User.objects.select_for_update().get(pk=uid, is_active=True)
            except (ValueError, TypeError, OverflowError, UnicodeError, User.DoesNotExist):
                raise ValidationError({'token': 'Invalid or expired recovery link.'})
            if not default_token_generator.check_token(user, data.validated_data['token']):
                raise ValidationError({'token': 'Invalid or expired recovery link.'})
            try:
                validate_password(data.validated_data['password'], user)
            except DjangoValidationError as exc:
                raise ValidationError({'password': exc.messages})
            user.set_password(data.validated_data['password'])
            user.save(update_fields=['password'])
        return Response({'detail': 'Password updated. Sign in again.'})
