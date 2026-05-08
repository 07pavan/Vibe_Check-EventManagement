"""
accounts/models.py

Custom User model with role-based access (Regular User / Event Organizer).
"""

from django.contrib.auth.models import AbstractUser
from django.db import models
from imagekit.models import ImageSpecField
from imagekit.processors import ResizeToFill


class User(AbstractUser):
    """
    Extended user model that adds a `role` field on top of Django's
    built-in AbstractUser (username, email, password, first_name, last_name …).
    """

    class Role(models.TextChoices):
        REGULAR = "regular", "Regular User"
        ORGANIZER = "organizer", "Event Organizer"

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.REGULAR,
        help_text="Defines what the user is allowed to do on the platform.",
    )

    # Make email unique so it can be used as a login identifier
    email = models.EmailField(unique=True)

    # Store an optional profile picture
    avatar = models.ImageField(
        upload_to="avatars/",
        null=True,
        blank=True,
    )

    # ------------------------------------------------------------------ #
    # Responsive avatar variants (virtual — no extra DB columns)
    # ------------------------------------------------------------------ #
    avatar_thumbnail = ImageSpecField(
        source="avatar",
        processors=[ResizeToFill(80, 80)],
        format="JPEG",
        options={"quality": 80},
    )
    avatar_medium = ImageSpecField(
        source="avatar",
        processors=[ResizeToFill(200, 200)],
        format="JPEG",
        options={"quality": 85},
    )

    bio = models.TextField(blank=True, default="")

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"
        ordering = ["-date_joined"]

    def __str__(self) -> str:
        return f"{self.username} ({self.get_role_display()})"

    # ------------------------------------------------------------------ #
    # Convenience helpers
    # ------------------------------------------------------------------ #
    @property
    def is_organizer(self) -> bool:
        return self.role == self.Role.ORGANIZER

    @property
    def is_regular(self) -> bool:
        return self.role == self.Role.REGULAR
