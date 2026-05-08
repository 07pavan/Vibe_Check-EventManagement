"""
events/serializers.py

Serializers for Event and Ticket models.

Responsive / device-aware behaviour
────────────────────────────────────
All list serializers read `context['device']` (set by DeviceAwareMixin in
views.py) and adjust their output accordingly:

  device=mobile   → compact payload: 9 fields + thumbnail only
  device=tablet   → medium payload:  all list fields + medium image
  device=desktop  → full payload:    all fields + all image sizes (default)

Image fields returned
─────────────────────
Every event response includes an `images` dict:
  {
    "original":  "<url> | null",
    "thumbnail": "<url> | null",   ← 400×267, ~30 kB
    "medium":    "<url> | null",   ← 800×534, ~80 kB
    "large":     "<url> | null"    ← 1200×800, ~180 kB
  }
Frontend picks the right size based on its breakpoint.
"""

from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import serializers

from accounts.serializers import PublicUserSerializer
from .models import Event, Ticket
from .utils import build_image_urls, get_device

User = get_user_model()


# ---------------------------------------------------------------------------
# Mobile-only field whitelist (EventListSerializer)
# ---------------------------------------------------------------------------
_MOBILE_EVENT_FIELDS = {
    "id", "title", "category", "category_display",
    "date", "venue_name", "price", "images",
    "tickets_remaining", "is_upcoming",
}


# --------------------------------------------------------------------------- #
# Event serializers
# --------------------------------------------------------------------------- #

class EventListSerializer(serializers.ModelSerializer):
    """
    Compact representation used for GET /api/events/.

    Responsive behaviour (set via ?device= query param):
      - mobile  → only _MOBILE_EVENT_FIELDS (no organizer, no lat/lng)
      - tablet  → all fields, images.medium highlighted
      - desktop → all fields + all image sizes (default)
    """

    organizer        = PublicUserSerializer(read_only=True)
    tickets_remaining = serializers.SerializerMethodField()
    is_upcoming      = serializers.BooleanField(read_only=True)
    category_display = serializers.CharField(read_only=True, source="get_category_display")

    # Responsive image dict — replaces the raw `image` URL field
    images = serializers.SerializerMethodField()

    def get_tickets_remaining(self, obj):
        val = getattr(obj, "_tickets_remaining", None)
        return val if val is not None else obj.tickets_remaining

    def get_images(self, obj):
        return build_image_urls(obj, "image", self.context.get("request"))

    def to_representation(self, instance):
        """Strip fields to the mobile-safe subset when device=mobile."""
        data = super().to_representation(instance)
        device = self.context.get("device", "desktop")
        if device == "mobile":
            return {k: v for k, v in data.items() if k in _MOBILE_EVENT_FIELDS}
        return data

    class Meta:
        model = Event
        fields = [
            "id",
            "title",
            "category",
            "category_display",
            "date",
            "venue_name",
            "price",
            "latitude",
            "longitude",
            "images",          # Replaces old `image` field — includes all sizes
            "organizer",
            "tickets_remaining",
            "is_upcoming",
            "is_published",
        ]


class EventDetailSerializer(serializers.ModelSerializer):
    """
    Full representation used for GET /api/events/<id>/.
    Always returns all fields regardless of device (detail pages use full data).
    """

    organizer        = PublicUserSerializer(read_only=True)
    tickets_remaining = serializers.SerializerMethodField()
    tickets_sold     = serializers.SerializerMethodField()
    is_upcoming      = serializers.BooleanField(read_only=True)
    category_display = serializers.CharField(read_only=True, source="get_category_display")
    images           = serializers.SerializerMethodField()

    def get_tickets_remaining(self, obj):
        val = getattr(obj, "_tickets_remaining", None)
        return val if val is not None else obj.tickets_remaining

    def get_tickets_sold(self, obj):
        val = getattr(obj, "_tickets_sold", None)
        return val if val is not None else obj.tickets_sold

    def get_images(self, obj):
        return build_image_urls(obj, "image", self.context.get("request"))

    class Meta:
        model = Event
        fields = [
            "id",
            "title",
            "description",
            "category",
            "category_display",
            "date",
            "venue_name",
            "price",
            "latitude",
            "longitude",
            "images",
            "organizer",
            "total_tickets",
            "tickets_sold",
            "tickets_remaining",
            "is_upcoming",
            "is_published",
            "created_at",
            "updated_at",
        ]


class EventCreateUpdateSerializer(serializers.ModelSerializer):
    """
    Used by Event Organizers to create or update events.
    Accepts `image` as a file upload; image spec variants are generated
    automatically on first access after save.
    """

    class Meta:
        model = Event
        fields = [
            "id",
            "title",
            "description",
            "category",
            "date",
            "venue_name",
            "price",
            "latitude",
            "longitude",
            "image",
            "total_tickets",
            "is_published",
        ]

    def validate_price(self, value):
        if value < 0:
            raise serializers.ValidationError("Price cannot be negative.")
        return value

    def validate_total_tickets(self, value):
        if value < 1:
            raise serializers.ValidationError("Must offer at least 1 ticket.")

        # On UPDATE only: prevent reducing below the already-sold count.
        # self.instance is None during creation, so we skip this check then.
        if self.instance is not None:
            tickets_sold = self.instance.tickets.count()
            if value < tickets_sold:
                raise serializers.ValidationError(
                    f"Cannot set total tickets to {value} — "
                    f"{tickets_sold} ticket(s) have already been sold for this event."
                )
        return value

    def create(self, validated_data):
        # Inject the organizer from the request context
        validated_data["organizer"] = self.context["request"].user
        return super().create(validated_data)


class OrganizerEventSerializer(serializers.ModelSerializer):
    """
    Organizer-specific event representation for GET /api/organizer/events/.

    Management fields:
      - tickets_sold      : count of tickets purchased
      - tickets_remaining : computed availability (from DB annotation)
      - revenue           : sum of price_paid (from DB annotation, no N+1)
      - status_label      : human-readable lifecycle label
      - scanned_count     : tickets scanned at door (from DB annotation, no N+1)
      - images            : all responsive image URLs
    """

    tickets_remaining = serializers.SerializerMethodField()
    tickets_sold      = serializers.SerializerMethodField()
    is_upcoming       = serializers.BooleanField(read_only=True)
    category_display  = serializers.CharField(read_only=True, source="get_category_display")
    images            = serializers.SerializerMethodField()

    # Derived management fields
    revenue       = serializers.SerializerMethodField()
    status_label  = serializers.SerializerMethodField()
    scanned_count = serializers.SerializerMethodField()

    def get_tickets_remaining(self, obj):
        val = getattr(obj, "_tickets_remaining", None)
        return val if val is not None else obj.tickets_remaining

    def get_tickets_sold(self, obj):
        val = getattr(obj, "_tickets_sold", None)
        return val if val is not None else obj.tickets_sold

    def get_images(self, obj):
        return build_image_urls(obj, "image", self.context.get("request"))

    def get_revenue(self, obj) -> str:
        """
        Reads from the `_revenue` annotation — no extra DB query (N+1 free).
        Falls back to a live aggregate when annotation is absent.
        """
        val = getattr(obj, "_revenue", None)
        if val is not None:
            return str(val)
        from django.db.models import Sum
        result = obj.tickets.aggregate(total=Sum("price_paid"))["total"]
        return str(result or "0.00")

    def get_status_label(self, obj) -> str:
        """Human-readable lifecycle status for dashboard badges."""
        if not obj.is_published:
            return "draft"
        if not obj.is_upcoming:
            return "past"
        remaining = getattr(obj, "_tickets_remaining", None)
        if remaining is None:
            remaining = obj.tickets_remaining
        if remaining == 0:
            return "sold_out"
        return "live"

    def get_scanned_count(self, obj) -> int:
        """
        Reads from the `_scanned_count` annotation — no extra DB query (N+1 free).
        Falls back to a live count when annotation is absent.
        """
        val = getattr(obj, "_scanned_count", None)
        if val is not None:
            return val
        return obj.tickets.filter(is_scanned=True).count()

    class Meta:
        model = Event
        fields = [
            "id",
            "title",
            "description",
            "category",
            "category_display",
            "date",
            "venue_name",
            "price",
            "latitude",
            "longitude",
            "images",
            "total_tickets",
            "tickets_sold",
            "tickets_remaining",
            "is_upcoming",
            "is_published",
            "status_label",
            "revenue",
            "scanned_count",
            "created_at",
            "updated_at",
        ]


# --------------------------------------------------------------------------- #
# Ticket serializers
# --------------------------------------------------------------------------- #

class TicketPurchaseSerializer(serializers.ModelSerializer):
    """
    Used for POST /api/tickets/purchase/.
    Accepts only `event` in the request body; everything else is derived.
    """

    class Meta:
        model = Ticket
        fields = ["event"]

    def validate_event(self, event):
        if not event.is_published:
            raise serializers.ValidationError("This event is not available.")
        if not event.is_upcoming:
            raise serializers.ValidationError("Cannot purchase a ticket for a past event.")
        if event.tickets_remaining == 0:
            raise serializers.ValidationError("Sorry, this event is sold out.")
        return event

    def validate(self, attrs):
        request = self.context["request"]
        event = attrs["event"]
        if Ticket.objects.filter(user=request.user, event=event).exists():
            raise serializers.ValidationError(
                {"event": "You already have a ticket for this event."}
            )
        return attrs

    def create(self, validated_data):
        """
        Atomic ticket creation with row-level DB lock to prevent overselling.
        """
        request = self.context["request"]
        event = validated_data["event"]

        with transaction.atomic():
            locked_event = (
                Event.objects
                .select_for_update()
                .get(pk=event.pk)
            )
            if locked_event.tickets_remaining == 0:
                raise serializers.ValidationError(
                    {"event": "Sorry, this event just sold out."}
                )
            ticket = Ticket.objects.create(
                user=request.user,
                event=locked_event,
                price_paid=locked_event.price,
            )
        return ticket


# Mobile-only ticket fields (compact wallet view)
_MOBILE_TICKET_FIELDS = {
    "id", "event", "ticket_hash", "qr_data",
    "event_status", "is_scanned", "purchased_at", "price_paid",
}


class TicketSerializer(serializers.ModelSerializer):
    """
    Full ticket representation returned after purchase or in user's ticket list.

    Responsive behaviour:
      - mobile  → compact subset (_MOBILE_TICKET_FIELDS)
      - desktop → full payload (default)

    Top-level convenience fields:
      - is_upcoming  : True if event is in the future
      - event_status : "Upcoming" | "Past" | "Used"
      - qr_data      : ticket_hash string to encode as QR code
    """

    event        = EventListSerializer(read_only=True)
    qr_data      = serializers.SerializerMethodField()
    is_upcoming  = serializers.SerializerMethodField()
    event_status = serializers.SerializerMethodField()

    class Meta:
        model = Ticket
        fields = [
            "id",
            "event",
            "ticket_hash",
            "qr_data",
            "is_upcoming",
            "event_status",
            "is_scanned",
            "scanned_at",
            "purchased_at",
            "price_paid",
        ]
        read_only_fields = fields

    def get_qr_data(self, obj) -> str:
        return obj.ticket_hash

    def get_is_upcoming(self, obj) -> bool:
        return obj.event.is_upcoming

    def get_event_status(self, obj) -> str:
        if obj.is_scanned:
            return "Used"
        return "Upcoming" if obj.event.is_upcoming else "Past"

    def to_representation(self, instance):
        """Strip to mobile-safe subset when device=mobile."""
        data = super().to_representation(instance)
        device = self.context.get("device", "desktop")
        if device == "mobile":
            return {k: v for k, v in data.items() if k in _MOBILE_TICKET_FIELDS}
        return data
