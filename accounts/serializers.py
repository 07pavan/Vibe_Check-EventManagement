"""
accounts/serializers.py

Serializers for User registration, profile, and JWT token handling.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

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
    """Handles new user sign-up including password confirmation."""

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
            "role",
            "password",
            "password2",
        ]

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

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "role",
            "avatar",
            "bio",
            "date_joined",
        ]
        read_only_fields = ["id", "username", "date_joined"]


class PublicUserSerializer(serializers.ModelSerializer):
    """Minimal public view of a user (e.g. event organizer info)."""

    class Meta:
        model = User
        fields = ["id", "username", "first_name", "last_name", "avatar"]
