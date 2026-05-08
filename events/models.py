"""
events/models.py

Event and Ticket models for the Local Event & Ticket Platform.
"""

import uuid
import hashlib

from django.conf import settings
from django.db import models
from django.utils import timezone


class Event(models.Model):
    """
    Represents a local event listed on the platform.
    """

    class Category(models.TextChoices):
        MUSIC = "music", "Music"
        TECH = "tech", "Tech"
        FOOD = "food", "Food"
        ARTS = "arts", "Arts"

    # ------------------------------------------------------------------ #
    # Core fields
    # ------------------------------------------------------------------ #
    title = models.CharField(max_length=255)
    description = models.TextField()
    category = models.CharField(
        max_length=10,
        choices=Category.choices,
        db_index=True,
    )
    date = models.DateTimeField(db_index=True)
    venue_name = models.CharField(max_length=255)
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Ticket price in USD. Set to 0.00 for free events.",
    )

    # ------------------------------------------------------------------ #
    # Location
    # ------------------------------------------------------------------ #
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        help_text="GPS latitude of the venue.",
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        help_text="GPS longitude of the venue.",
    )

    # ------------------------------------------------------------------ #
    # Media
    # ------------------------------------------------------------------ #
    image = models.ImageField(
        upload_to="events/images/",
        null=True,
        blank=True,
        help_text="Poster or banner image for the event.",
    )

    # ------------------------------------------------------------------ #
    # Relationships & metadata
    # ------------------------------------------------------------------ #
    organizer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="organized_events",
        help_text="The Event Organizer who created this event.",
    )
    total_tickets = models.PositiveIntegerField(
        default=100,
        help_text="Maximum number of tickets available.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_published = models.BooleanField(
        default=True,
        help_text="Unpublished events are hidden from public listings.",
    )

    class Meta:
        verbose_name = "Event"
        verbose_name_plural = "Events"
        ordering = ["date"]

    def __str__(self) -> str:
        return f"{self.title} — {self.date:%Y-%m-%d}"

    @property
    def tickets_sold(self) -> int:
        return self.tickets.count()

    @property
    def tickets_remaining(self) -> int:
        return max(self.total_tickets - self.tickets_sold, 0)

    @property
    def is_upcoming(self) -> bool:
        return self.date > timezone.now()


# --------------------------------------------------------------------------- #


class Ticket(models.Model):
    """
    Represents a purchased ticket linking a User to an Event.

    `ticket_hash` is a SHA-256-based unique string used for QR-code generation.
    """

    # ------------------------------------------------------------------ #
    # Relationships
    # ------------------------------------------------------------------ #
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="tickets",
    )
    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name="tickets",
    )

    # ------------------------------------------------------------------ #
    # Ticket identity
    # ------------------------------------------------------------------ #
    ticket_hash = models.CharField(
        max_length=64,
        unique=True,
        editable=False,
        db_index=True,
        help_text="Unique SHA-256 hash — encode this in a QR code.",
    )

    # ------------------------------------------------------------------ #
    # Scan / entry tracking
    # ------------------------------------------------------------------ #
    is_scanned = models.BooleanField(
        default=False,
        help_text="Flipped to True when the QR code is scanned at the door.",
    )
    scanned_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when the ticket was scanned.",
    )

    # ------------------------------------------------------------------ #
    # Purchase metadata
    # ------------------------------------------------------------------ #
    purchased_at = models.DateTimeField(auto_now_add=True)
    price_paid = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Price at the time of purchase (snapshot).",
    )

    class Meta:
        verbose_name = "Ticket"
        verbose_name_plural = "Tickets"
        ordering = ["-purchased_at"]
        # Prevent duplicate purchases: one user ↔ one event
        unique_together = [("user", "event")]

    # ------------------------------------------------------------------ #
    # Hash generation
    # ------------------------------------------------------------------ #
    @staticmethod
    def _generate_hash(user_id: int, event_id: int) -> str:
        """
        Derive a deterministic-but-opaque hash from user + event + a random UUID.
        The UUID guarantees uniqueness even if the same pair re-purchases after
        a refund scenario is added later.
        """
        raw = f"{user_id}-{event_id}-{uuid.uuid4()}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def save(self, *args, **kwargs):
        if not self.ticket_hash:
            self.ticket_hash = self._generate_hash(self.user_id, self.event_id)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"Ticket #{self.pk} — {self.user.username} @ {self.event.title}"

    def mark_scanned(self) -> None:
        """Mark this ticket as scanned and record the timestamp."""
        self.is_scanned = True
        self.scanned_at = timezone.now()
        self.save(update_fields=["is_scanned", "scanned_at"])


# --------------------------------------------------------------------------- #


class UserEventLike(models.Model):
    """
    Represents a user 'liking' (saving/bookmarking) an event.

    The unique_together constraint ensures a user can only like
    a given event once. Attempting a duplicate raises IntegrityError
    at the DB level, which the view catches and treats as a no-op.

    Both FKs use CASCADE so that likes are automatically removed when
    the user account or the event is deleted.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="liked_events",
        help_text="The user who liked this event.",
    )
    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name="likes",
        help_text="The event that was liked.",
    )
    liked_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when the like was created.",
    )

    class Meta:
        verbose_name = "User Event Like"
        verbose_name_plural = "User Event Likes"
        # Core constraint: one like per user per event
        unique_together = [("user", "event")]
        ordering = ["-liked_at"]

    def __str__(self) -> str:
        return f"{self.user.username} ❤ {self.event.title}"
