"""
accounts/serializers.py

Serializers for User registration, profile, and JWT token handling.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

# Import image URL builder (avoids circular imports — events → accounts is fine)
from events.utils import build_image_urls

User = get_user_model()


# --------------------------------------------------------------------------- #
# JWT — enriched token payload
# --------------------------------------------------------------------------- #

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Add user role and username to the JWT payload."""

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["username"] = user.username
        token["role"] = user.role
        token["email"] = user.email
        return token


# --------------------------------------------------------------------------- #
# User serializers
# --------------------------------------------------------------------------- #

class UserRegistrationSerializer(serializers.ModelSerializer):
    """
    Handles new user sign-up including password confirmation.

    Security note: `role` is intentionally excluded from this serializer.
    All new accounts are created as `regular` users (the model default).
    Elevation to `organizer` is performed exclusively through Django Admin
    to prevent privilege self-escalation via the API.
    """

    password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password],
    )
    password2 = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "password",
            "password2",
        ]
        # `role` is NOT listed here — model default (regular) always applies.

    def validate(self, attrs):
        if attrs["password"] != attrs.pop("password2"):
            raise serializers.ValidationError(
                {"password": "Password fields did not match."}
            )
        return attrs

    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        return user


class UserProfileSerializer(serializers.ModelSerializer):
    """Read / update current user's profile."""

    avatar_urls = serializers.SerializerMethodField(
        help_text="Responsive avatar URLs: thumbnail (80×80) and medium (200×200)."
    )

    def get_avatar_urls(self, obj):
        """
        Returns:
            {
                "original":  "<url> | null",
                "thumbnail": "<url> | null",  ← 80×80 px
                "medium":    "<url> | null"   ← 200×200 px
            }
        """
        return build_image_urls(obj, "avatar", self.context.get("request"))

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "role",
            "avatar",          # Original upload URL (kept for backward compat)
            "avatar_urls",     # Responsive size dict
            "bio",
            "date_joined",
        ]
        read_only_fields = ["id", "username", "role", "date_joined", "avatar_urls"]


class PublicUserSerializer(serializers.ModelSerializer):
    """Minimal public view of a user (e.g. event organizer info on event cards)."""

    avatar_urls = serializers.SerializerMethodField()

    def get_avatar_urls(self, obj):
        return build_image_urls(obj, "avatar", self.context.get("request"))

    class Meta:
        model = User
        fields = ["id", "username", "first_name", "last_name", "avatar", "avatar_urls"]
