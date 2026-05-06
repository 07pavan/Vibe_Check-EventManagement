"""
events/views.py

API views for Events and Tickets.

Endpoints implemented
─────────────────────
GET    /api/events/              — list all published events (filterable)
POST   /api/events/              — create event (Organizer only)
GET    /api/events/<id>/         — retrieve single event
PUT    /api/events/<id>/         — update event (owner Organizer only)
PATCH  /api/events/<id>/         — partial update
DELETE /api/events/<id>/         — delete event (owner Organizer only)

GET    /api/organizer/events/    — list ALL events owned by logged-in organizer (incl. drafts)

POST   /api/tickets/purchase/    — purchase a ticket (authenticated users)
GET    /api/user/tickets/        — list own tickets

POST   /api/tickets/<id>/scan/   — mark ticket as scanned via URL hash (Organizer only)
POST   /api/tickets/verify/      — verify & scan ticket via body hash (QR scanner, Organizer only)
"""

from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status, filters
from rest_framework.response import Response
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend

from .filters import EventFilter
from .models import Event, Ticket
from .serializers import (
    EventListSerializer,
    EventDetailSerializer,
    EventCreateUpdateSerializer,
    OrganizerEventSerializer,
    TicketPurchaseSerializer,
    TicketSerializer,
)


# --------------------------------------------------------------------------- #
# Custom permissions
# --------------------------------------------------------------------------- #

class IsOrganizerOrReadOnly(permissions.BasePermission):
    """
    - GET/HEAD/OPTIONS: available to anyone (public).
    - Write operations: only for authenticated Event Organizers.
    """
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return (
            request.user
            and request.user.is_authenticated
            and request.user.is_organizer
        )


class IsEventOwnerOrReadOnly(permissions.BasePermission):
    """Object-level: only the organizer who created the event can modify it."""
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.organizer == request.user


# --------------------------------------------------------------------------- #
# Event Views
# --------------------------------------------------------------------------- #

class EventListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/events/  — public list with filtering
    POST /api/events/  — create (Organizer only)
    """
    permission_classes = [IsOrganizerOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = EventFilter
    search_fields = ["title", "description", "venue_name"]
    ordering_fields = ["date", "price", "created_at"]
    ordering = ["date"]

    def get_queryset(self):
        """Only show published events in public listing."""
        qs = Event.objects.select_related("organizer").filter(is_published=True)
        return qs

    def get_serializer_class(self):
        if self.request.method == "POST":
            return EventCreateUpdateSerializer
        return EventListSerializer

    def perform_create(self, serializer):
        serializer.save(organizer=self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        event = serializer.save(organizer=request.user)
        # Return the full detail view on creation
        output = EventDetailSerializer(event, context={"request": request})
        return Response(output.data, status=status.HTTP_201_CREATED)


class EventDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET    /api/events/<id>/  — retrieve
    PUT    /api/events/<id>/  — update (owner only)
    PATCH  /api/events/<id>/  — partial update (owner only)
    DELETE /api/events/<id>/  — delete (owner only)
    """
    queryset = Event.objects.select_related("organizer").all()
    permission_classes = [IsOrganizerOrReadOnly, IsEventOwnerOrReadOnly]

    def get_serializer_class(self):
        if self.request.method in ("PUT", "PATCH"):
            return EventCreateUpdateSerializer
        return EventDetailSerializer


class OrganizerEventListView(generics.ListAPIView):
    """
    GET /api/organizer/events/

    Returns ALL events that belong to the currently authenticated organizer,
    including unpublished drafts and past events — unlike the public
    /api/events/ endpoint which filters to published + upcoming only.

    Supports ordering: ?ordering=date | -date | price | created_at
    Auth: Bearer token — Organizer only.
    """
    serializer_class = OrganizerEventSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.OrderingFilter, filters.SearchFilter]
    ordering_fields = ["date", "price", "created_at", "tickets_sold"]
    ordering = ["-created_at"]
    search_fields = ["title", "venue_name"]

    def get_queryset(self):
        if not self.request.user.is_organizer:
            return Event.objects.none()
        return (
            Event.objects
            .select_related("organizer")
            .prefetch_related("tickets")
            .filter(organizer=self.request.user)
        )


# --------------------------------------------------------------------------- #
# Ticket Views
# --------------------------------------------------------------------------- #

class TicketPurchaseView(generics.CreateAPIView):
    """
    POST /api/tickets/purchase/

    Body: { "event": <event_id> }
    Auth: Bearer token required.

    Business rules enforced in the serializer:
      - Event must be published & upcoming
      - Event must not be sold out
      - User can only buy one ticket per event
    """
    serializer_class = TicketPurchaseSerializer
    permission_classes = [permissions.IsAuthenticated]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ticket = serializer.save()
        output = TicketSerializer(ticket, context={"request": request})
        return Response(output.data, status=status.HTTP_201_CREATED)


class UserTicketListView(generics.ListAPIView):
    """
    GET /api/user/tickets/

    Returns all tickets owned by the currently authenticated user.
    Auth: Bearer token required.
    """
    serializer_class = TicketSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["purchased_at", "event__date"]
    ordering = ["-purchased_at"]

    def get_queryset(self):
        return (
            Ticket.objects
            .select_related("user", "event", "event__organizer")
            .filter(user=self.request.user)
        )


class TicketScanView(APIView):
    """
    POST /api/tickets/<ticket_hash>/scan/

    Marks a ticket as scanned at the door.
    Only accessible to Event Organizers.

    Body: {} (empty — ticket identified via URL hash)
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, ticket_hash):
        if not request.user.is_organizer:
            return Response(
                {"detail": "Only Event Organizers can scan tickets."},
                status=status.HTTP_403_FORBIDDEN,
            )

        ticket = get_object_or_404(Ticket, ticket_hash=ticket_hash)

        # Verify the organizer owns the related event
        if ticket.event.organizer != request.user:
            return Response(
                {"detail": "You do not own this event."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if ticket.is_scanned:
            return Response(
                {
                    "status": "already_scanned",
                    "scanned_at": ticket.scanned_at,
                    "detail": "This ticket was already scanned.",
                },
                status=status.HTTP_409_CONFLICT,
            )

        ticket.mark_scanned()
        output = TicketSerializer(ticket, context={"request": request})
        return Response(
            {"status": "success", "ticket": output.data},
            status=status.HTTP_200_OK,
        )


class TicketVerifyView(APIView):
    """
    POST /api/tickets/verify/

    Accepts a ticket_hash in the request body, checks if the ticket exists,
    and marks it as scanned. Designed to be called by a QR code scanner.

    Body: { "ticket_hash": "<64-char SHA-256 hash>" }
    Auth: Bearer token — Organizer only.

    Responses:
      200 — { "status": "access_granted",  "ticket": {...} }
      409 — { "status": "already_scanned", "scanned_at": "...", "detail": "..." }
      403 — not an organizer
      404 — ticket hash not found
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        # ── Auth check ─────────────────────────────────────────────────────
        if not request.user.is_organizer:
            return Response(
                {"detail": "Only Event Organizers can verify tickets."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # ── Validate input ─────────────────────────────────────────────────
        ticket_hash = request.data.get("ticket_hash", "").strip()
        if not ticket_hash:
            return Response(
                {"detail": "ticket_hash is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ── Fetch ticket ───────────────────────────────────────────────────
        ticket = get_object_or_404(
            Ticket.objects.select_related("user", "event", "event__organizer"),
            ticket_hash=ticket_hash,
        )

        # ── Ownership check ────────────────────────────────────────────────
        if ticket.event.organizer != request.user:
            return Response(
                {
                    "detail": "You do not own this event and cannot verify its tickets.",
                    "event": ticket.event.title,
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # ── Already scanned? ───────────────────────────────────────────────
        if ticket.is_scanned:
            return Response(
                {
                    "status": "already_scanned",
                    "scanned_at": ticket.scanned_at,
                    "ticket_hash": ticket.ticket_hash,
                    "event": ticket.event.title,
                    "user": ticket.user.username,
                    "detail": f"Ticket already scanned at {ticket.scanned_at:%Y-%m-%d %H:%M:%S UTC}.",
                },
                status=status.HTTP_409_CONFLICT,
            )

        # ── Mark as scanned ────────────────────────────────────────────────
        ticket.mark_scanned()
        output = TicketSerializer(ticket, context={"request": request})
        return Response(
            {
                "status": "access_granted",
                "ticket": output.data,
            },
            status=status.HTTP_200_OK,
        )
