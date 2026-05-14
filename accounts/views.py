"""
accounts/views.py

Auth and user-profile API views.

Rate limiting strategy:
  All endpoints are protected by DRF's AnonRateThrottle + UserRateThrottle
  configured globally in settings.REST_FRAMEWORK. We do NOT use
  django_ratelimit here — two separate rate-limiting systems on the same
  view conflict and produce inconsistent behavior (one may block while
  the other passes). DRF throttling is the single source of truth.
"""

from django.contrib.auth import get_user_model
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView

from .serializers import (
    CustomTokenObtainPairSerializer,
    UserRegistrationSerializer,
    UserProfileSerializer,
)

User = get_user_model()


class CustomTokenObtainPairView(TokenObtainPairView):
    """
    POST /api/auth/token/

    Returns an access + refresh JWT pair enriched with role & username.

    Rate limiting: handled globally by DRF AnonRateThrottle (60/min).
    The previous django_ratelimit decorator has been removed to avoid
    two conflicting rate-limit systems on the same endpoint.

    Responses:
      200 — { access, refresh }
      401 — bad credentials
      429 — rate limit exceeded (DRF throttle)
    """
    serializer_class = CustomTokenObtainPairSerializer


class RegisterView(generics.CreateAPIView):
    """
    POST /api/auth/register/

    Open endpoint — no authentication required.
    Creates a new regular user account. Role is always 'regular'
    regardless of what the client sends.

    Rate limiting: handled globally by DRF AnonRateThrottle (60/min).
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
                    "role": user.role,   # Always "regular" — confirmed by serializer
                },
            },
            status=status.HTTP_201_CREATED,
        )


class UserProfileView(generics.RetrieveUpdateAPIView):
    """
    GET   /api/auth/profile/  — retrieve own profile
    PATCH /api/auth/profile/  — partial update own profile

    WHY PATCH only (not PUT):
    PUT requires ALL fields to be sent — if a client omits `avatar`,
    the avatar gets wiped. PATCH allows sending only the fields being
    changed. We enforce `partial=True` on PATCH calls automatically via
    `http_method_names` limiting and DRF's partial update logic.

    Writable: first_name, last_name, bio, avatar
    Read-only: id, username, role, email, date_joined
    """
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
    # Disable PUT — profile updates must use PATCH (partial update only)
    http_method_names = ["get", "patch", "head", "options"]

    def get_object(self):
        return self.request.user

    def partial_update(self, request, *args, **kwargs):
        """Force partial=True so omitted fields are not wiped."""
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)


class LogoutView(generics.GenericAPIView):
    """
    POST /api/auth/logout/

    Accepts a refresh token in the request body and blacklists it,
    invalidating the session server-side. The client must also
    clear its local token storage (localStorage/sessionStorage).

    Body: { "refresh": "<refresh-token>" }
    Auth: Bearer token required.

    WHY blacklist on logout:
    JWTs are stateless — there is no server session to destroy.
    The only way to truly invalidate a JWT before expiry is to
    track it in a blacklist. SimpleJWT's token_blacklist app
    provides this. Without blacklisting, a logged-out user's
    stolen refresh token remains valid for 7 days.

    Responses:
      205 — token blacklisted successfully
      400 — missing or invalid/already-blacklisted refresh token
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
            # Token already blacklisted or malformed — treat as logout success
            # to avoid leaking information about token state
            return Response(
                {"detail": "Token is invalid or already blacklisted."},
                status=status.HTTP_400_BAD_REQUEST,
            )


class IsOrganizerCheckView(generics.GenericAPIView):
    """
    GET /api/auth/is-organizer/

    Lightweight gate check used by the scanner page on load.
    Confirms the authenticated user holds the organizer role.
    Auth: Bearer token required.

    Responses:
      200 — { "is_organizer": true,  "username": "...", "role": "organizer" }
      403 — { "is_organizer": false, "detail": "Access denied..." }
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
