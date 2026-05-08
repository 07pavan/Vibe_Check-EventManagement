"""
accounts/views.py

Auth and user-profile API views.
"""

from django.contrib.auth import get_user_model
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView

from .serializers import (
    CustomTokenObtainPairSerializer,
    UserRegistrationSerializer,
    UserProfileSerializer,
    PasswordResetRequestSerializer,
    PasswordResetConfirmSerializer,
)

User = get_user_model()


@method_decorator(
    ratelimit(key="ip", rate="10/m", method="POST", block=True),
    name="post"
)
class CustomTokenObtainPairView(TokenObtainPairView):
    """
    POST /api/auth/token/
    Returns an access + refresh JWT pair enriched with role & username.
    Rate-limited to 10 attempts/minute per IP to prevent brute-force attacks.
    """
    serializer_class = CustomTokenObtainPairSerializer


class RegisterView(generics.CreateAPIView):
    """
    POST /api/auth/register/
    Open endpoint — no authentication required.
    """
    queryset = User.objects.all()
    permission_classes = [permissions.AllowAny]
    serializer_class = UserRegistrationSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(
            {
                "message": "Account created successfully.",
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "role": user.role,
                },
            },
            status=status.HTTP_201_CREATED,
        )


class UserProfileView(generics.RetrieveUpdateAPIView):
    """
    GET  /api/auth/profile/  — retrieve own profile
    PATCH /api/auth/profile/ — partial update own profile
    """
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


class LogoutView(generics.GenericAPIView):
    """
    POST /api/auth/logout/

    Accepts a refresh token in the request body and blacklists it,
    invalidating the session server-side. The client should also
    clear its local token storage.

    Body: { "refresh": "<refresh-token>" }
    Auth: Bearer token required.

    Responses:
      205 — token blacklisted successfully
      400 — missing or invalid refresh token
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        from rest_framework_simplejwt.tokens import RefreshToken
        from rest_framework_simplejwt.exceptions import TokenError

        refresh_token = request.data.get("refresh")
        if not refresh_token:
            return Response(
                {"detail": "Refresh token is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response(
                {"detail": "Successfully logged out."},
                status=status.HTTP_205_RESET_CONTENT,
            )
        except TokenError:
            return Response(
                {"detail": "Token is invalid or already blacklisted."},
                status=status.HTTP_400_BAD_REQUEST,
            )


class IsOrganizerCheckView(generics.GenericAPIView):
    """
    GET /api/auth/is-organizer/

    Lightweight gate check used by the scanner page on load.
    Auth: Bearer token required.

    Responses:
      200 — { "is_organizer": true,  "username": "...", "role": "organizer" }
      403 — { "is_organizer": false, "detail": "Access denied. Organizer role required." }
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if not request.user.is_organizer:
            return Response(
                {
                    "is_organizer": False,
                    "detail": "Access denied. Organizer role required.",
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        return Response(
            {
                "is_organizer": True,
                "username": request.user.username,
                "role": request.user.role,
                "email": request.user.email,
            },
            status=status.HTTP_200_OK,
        )


# --------------------------------------------------------------------------- #
# Password Reset Views
# --------------------------------------------------------------------------- #

class PasswordResetRequestView(generics.GenericAPIView):
    """
    POST /api/auth/password/reset/

    Generates a one-time password reset link and sends it to the user's
    registered email address.

    Body: { "email": "user@example.com" }
    Auth: None required (user is logged out when resetting password).

    Security:
      - Always returns HTTP 200 with the same message, regardless of
        whether the email is registered (prevents user enumeration).
      - Token is generated by Django's default_token_generator, which
        invalidates automatically on password change or after
        PASSWORD_RESET_TIMEOUT seconds (default: 3 days).

    Responses:
      200 — { "detail": "If this email is registered, a reset link has been sent." }
      400 — invalid email format
    """
    permission_classes = [permissions.AllowAny]
    serializer_class   = PasswordResetRequestSerializer

    def post(self, request):
        from django.contrib.auth.tokens import default_token_generator
        from django.utils.http import urlsafe_base64_encode
        from django.utils.encoding import force_bytes
        from django.core.mail import send_mail
        from django.conf import settings as django_settings

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]

        # Generic response — always the same whether email exists or not
        GENERIC_RESPONSE = {
            "detail": "If this email is registered, a reset link has been sent."
        }

        try:
            user = User.objects.get(email=email, is_active=True)
        except User.DoesNotExist:
            # Do NOT reveal that the email isn't registered
            return Response(GENERIC_RESPONSE, status=status.HTTP_200_OK)

        # Build the one-time token and UID
        uid   = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)

        # Build reset URL — frontend must handle this route and call the
        # confirm endpoint with the uid + token extracted from the URL.
        frontend_url = getattr(
            django_settings,
            "FRONTEND_URL",
            "http://localhost:8000",
        )
        reset_link = f"{frontend_url}/reset-password?uid={uid}&token={token}"

        # Send email
        send_mail(
            subject="GoAttend — Password Reset Request",
            message=(
                f"Hi {user.first_name or user.username},\n\n"
                f"You requested a password reset for your GoAttend account.\n\n"
                f"Click the link below to set a new password (valid for 3 days):\n"
                f"{reset_link}\n\n"
                f"If you did not request this, please ignore this email.\n\n"
                f"— The GoAttend Team"
            ),
            from_email=getattr(django_settings, "DEFAULT_FROM_EMAIL", "noreply@goattend.app"),
            recipient_list=[user.email],
            fail_silently=False,
        )

        return Response(GENERIC_RESPONSE, status=status.HTTP_200_OK)


class PasswordResetConfirmView(generics.GenericAPIView):
    """
    POST /api/auth/password/reset/confirm/

    Validates the UID + token pair and sets the user's new password.
    All token/UID decoding and validation is handled in
    PasswordResetConfirmSerializer.validate().

    Body:
      {
        "uid":           "<base64-encoded user pk>",
        "token":         "<one-time reset token>",
        "new_password":  "<new password>",
        "new_password2": "<confirmation>"
      }
    Auth: None required.

    Responses:
      200 — { "detail": "Password has been reset successfully." }
      400 — invalid token, mismatched passwords, or failed validation
    """
    permission_classes = [permissions.AllowAny]
    serializer_class   = PasswordResetConfirmSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # The serializer already decoded + verified the user and token
        user = serializer.validated_data["user"]
        user.set_password(serializer.validated_data["new_password"])
        user.save(update_fields=["password"])

        return Response(
            {"detail": "Password has been reset successfully."},
            status=status.HTTP_200_OK,
        )

