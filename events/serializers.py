"""
events/serializers.py

Serializers for Event and Ticket models.
"""

from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import serializers

from accounts.serializers import PublicUserSerializer
from .models import Event, Ticket

User = get_user_model()


# --------------------------------------------------------------------------- #
# Event serializers
# --------------------------------------------------------------------------- #

class EventListSerializer(serializers.ModelSerializer):
    """
    Compact representation used for GET /api/events/.
    Includes computed fields: tickets_remaining, is_upcoming.
    """

    organizer = PublicUserSerializer(read_only=True)
    tickets_remaining = serializers.SerializerMethodField()
    is_upcoming = serializers.BooleanField(read_only=True)
    category_display = serializers.CharField(read_only=True, source="get_category_display")

    def get_tickets_remaining(self, obj):
        # Use DB annotation if available (list view), else Python property (detail view)
        val = getattr(obj, "_tickets_remaining", None)
        return val if val is not None else obj.tickets_remaining

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
            "image",
            "organizer",
            "tickets_remaining",
            "is_upcoming",
            "is_published",
        ]


class EventDetailSerializer(serializers.ModelSerializer):
    """
    Full representation used for a single event detail view.
    """

    organizer = PublicUserSerializer(read_only=True)
    tickets_remaining = serializers.SerializerMethodField()
    tickets_sold = serializers.SerializerMethodField()
    is_upcoming = serializers.BooleanField(read_only=True)
    category_display = serializers.CharField(read_only=True, source="get_category_display")

    def get_tickets_remaining(self, obj):
        val = getattr(obj, "_tickets_remaining", None)
        return val if val is not None else obj.tickets_remaining

    def get_tickets_sold(self, obj):
        val = getattr(obj, "_tickets_sold", None)
        return val if val is not None else obj.tickets_sold

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
            "image",
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
    Organizer is automatically set to the requesting user.
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
        return value

    def create(self, validated_data):
        # Inject the organizer from the request context
        validated_data["organizer"] = self.context["request"].user
        return super().create(validated_data)


class OrganizerEventSerializer(serializers.ModelSerializer):
    """
    Organizer-specific event representation for GET /api/organizer/events/.

    Extends the public detail view with management fields:
      - tickets_sold     : count of tickets purchased
      - tickets_remaining: computed availability
      - revenue          : tickets_sold × price (snapshot revenue)
      - status           : human-readable lifecycle label
      - scanned_count    : how many tickets have been scanned at door
    """

    tickets_remaining = serializers.SerializerMethodField()
    tickets_sold      = serializers.SerializerMethodField()
    is_upcoming       = serializers.BooleanField(read_only=True)
    category_display  = serializers.CharField(read_only=True, source="get_category_display")

    def get_tickets_remaining(self, obj):
        val = getattr(obj, "_tickets_remaining", None)
        return val if val is not None else obj.tickets_remaining

    def get_tickets_sold(self, obj):
        val = getattr(obj, "_tickets_sold", None)
        return val if val is not None else obj.tickets_sold

    # Derived management fields
    revenue       = serializers.SerializerMethodField()
    status_label  = serializers.SerializerMethodField()
    scanned_count = serializers.SerializerMethodField()

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
            "image",
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

    def get_revenue(self, obj) -> str:
        """Total revenue = sum of price_paid across all tickets for this event."""
        from django.db.models import Sum
        result = obj.tickets.aggregate(total=Sum("price_paid"))["total"]
        return str(result or "0.00")

    def get_status_label(self, obj) -> str:
        """Human-readable lifecycle status for dashboard badges."""
        if not obj.is_published:
            return "draft"
        if not obj.is_upcoming:
            return "past"
        if obj.tickets_remaining == 0:
            return "sold_out"
        return "live"

    def get_scanned_count(self, obj) -> int:
        """Number of tickets already scanned at the door."""
        return obj.tickets.filter(is_scanned=True).count()


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
        # Ensure the event is published and upcoming
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
        # Prevent duplicate purchases
        if Ticket.objects.filter(user=request.user, event=event).exists():
            raise serializers.ValidationError(
                {"event": "You already have a ticket for this event."}
            )
        return attrs

    def create(self, validated_data):
        """
        Atomic ticket creation with row-level DB lock to prevent overselling.
        select_for_update() acquires a PostgreSQL FOR UPDATE lock on the Event
        row so no two concurrent requests can both read tickets_remaining > 0
        and both succeed in creating a ticket beyond total_tickets.
        """
        request = self.context["request"]
        event = validated_data["event"]

        with transaction.atomic():
            # Lock the specific event row for the duration of this transaction
            locked_event = (
                Event.objects
                .select_for_update()
                .get(pk=event.pk)
            )
            # Re-check availability under the lock (guards against race)
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


class TicketSerializer(serializers.ModelSerializer):
    """
    Full ticket representation returned after purchase or in user's ticket list.

    Top-level fields for convenience (mirrors event nested data):
      - is_upcoming    : True if event is in the future
      - event_status   : human-readable label — "Upcoming" | "Past" | "Used"
      - qr_data        : ticket_hash string to encode as QR code
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
        read_only_fields = fields  # All fields are read-only on output

    def get_qr_data(self, obj) -> str:
        """
        Returns the string that should be encoded in the QR code.
        Format: <ticket_hash>  (the backend validates this on scan)
        """
        return obj.ticket_hash

    def get_is_upcoming(self, obj) -> bool:
        """True if the related event is still in the future."""
        return obj.event.is_upcoming

    def get_event_status(self, obj) -> str:
        """
        Human-readable status for the ticket wallet UI.
          'Used'     — ticket was already scanned at the door
          'Upcoming' — event is in the future and ticket is valid
          'Past'     — event has already happened
        """
        if obj.is_scanned:
            return "Used"
        return "Upcoming" if obj.event.is_upcoming else "Past"
