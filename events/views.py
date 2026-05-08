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
from django.db.models import Count, F, ExpressionWrapper, IntegerField, Q, Sum
from rest_framework import generics, permissions, status, filters
from rest_framework.response import Response
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend

from .filters import EventFilter
from .models import Event, Ticket, UserEventLike
from .permissions import IsOrganizer, IsOrganizerOrReadOnly, IsEventOwnerOrReadOnly
from .serializers import (
    EventListSerializer,
    EventDetailSerializer,
    EventCreateUpdateSerializer,
    OrganizerEventSerializer,
    TicketPurchaseSerializer,
    TicketSerializer,
)


# Permission classes are defined in events/permissions.py
# IsOrganizer, IsOrganizerOrReadOnly, IsEventOwnerOrReadOnly
# are imported above and applied per-view.


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
        """Only show published events — tickets_remaining annotated at DB level to avoid N+1."""
        return (
            Event.objects
            .select_related("organizer")
            .filter(is_published=True)
            .annotate(
                _tickets_sold=Count("tickets"),
                _tickets_remaining=ExpressionWrapper(
                    F("total_tickets") - Count("tickets"),
                    output_field=IntegerField(),
                ),
            )
        )

    def get_serializer_context(self):
        """
        Inject a pre-fetched set of liked event IDs into serializer context.

        For an authenticated user, this runs ONE extra query to fetch all
        liked event PKs, stores them as a Python set in the context, and
        lets EventListSerializer.get_is_liked() do an O(1) `in` check
        instead of one DB query per event row.

        Anonymous users get an empty set (no DB query needed).
        """
        ctx = super().get_serializer_context()
        request = ctx.get("request")
        if request and request.user and request.user.is_authenticated:
            liked_ids = set(
                UserEventLike.objects
                .filter(user=request.user)
                .values_list("event_id", flat=True)
            )
        else:
            liked_ids = set()
        ctx["_user_likes_ids"] = liked_ids
        return ctx

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
        """
        Returns the organizer's events fully annotated at DB level:
          _tickets_sold      — total tickets purchased
          _tickets_remaining — seats still available
          _scanned_count     — tickets already scanned at the door
          _revenue           — total price_paid across all tickets

        All four values are computed in a SINGLE query, eliminating the
        N+1 that previously existed for scanned_count and revenue.
        """
        return (
            Event.objects
            .select_related("organizer")
            .filter(organizer=self.request.user)
            .annotate(
                _tickets_sold=Count("tickets"),
                _tickets_remaining=ExpressionWrapper(
                    F("total_tickets") - Count("tickets"),
                    output_field=IntegerField(),
                ),
                # Count only the scanned tickets (conditional aggregate)
                _scanned_count=Count(
                    "tickets",
                    filter=Q(tickets__is_scanned=True),
                ),
                # Sum of price_paid across all tickets for this event
                _revenue=Sum("tickets__price_paid"),
            )
        )

    def get(self, request, *args, **kwargs):
        """Return 403 explicitly for non-organizers instead of empty 200."""
        if not request.user.is_organizer:
            return Response(
                {"detail": "Only Event Organizers can access this endpoint."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().get(request, *args, **kwargs)


class EventAttendeesView(APIView):
    """
    GET /api/organizer/events/<event_id>/attendees/

    Returns all ticket holders for one of the organizer's events.
    Auth: Bearer token — Organizer only, and must own the event.

    Response per ticket:
      id, ticket_hash, is_scanned, scanned_at, price_paid,
      purchased_at, attendee: {username, email, full_name}
    """
    permission_classes = [IsOrganizer]

    def get(self, request, event_id):
        event = get_object_or_404(Event, pk=event_id)

        # Must own this event
        if event.organizer != request.user:
            return Response(
                {"detail": "You do not own this event."},
                status=status.HTTP_403_FORBIDDEN,
            )

        tickets = (
            Ticket.objects
            .select_related("user")
            .filter(event=event)
            .order_by("-purchased_at")
        )

        data = [
            {
                "id":           t.id,
                "ticket_hash":  t.ticket_hash,
                "is_scanned":   t.is_scanned,
                "scanned_at":   t.scanned_at,
                "price_paid":   str(t.price_paid),
                "purchased_at": t.purchased_at,
                "attendee": {
                    "username":   t.user.username,
                    "email":      t.user.email,
                    "full_name":  t.user.get_full_name() or t.user.username,
                },
            }
            for t in tickets
        ]

        return Response(
            {
                "event_id":    event.id,
                "event_title": event.title,
                "total":       len(data),
                "attended":    sum(1 for t in tickets if t.is_scanned),
                "attendees":   data,
            },
            status=status.HTTP_200_OK,
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

    Sorting:
      Default — upcoming events first (sorted by event date ASC),
                then past events (sorted by event date DESC).
      Override with ?ordering=purchased_at | event__date

    Filtering:
      ?status=upcoming  — events whose date > now and not yet scanned
      ?status=past      — events whose date <= now
      ?status=used      — tickets that have already been scanned
    """
    serializer_class = TicketSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["purchased_at", "event__date"]

    def get_queryset(self):
        from django.utils import timezone
        from django.db.models import Case, When, Value, IntegerField

        now = timezone.now()
        status_filter = self.request.query_params.get("status", "").lower()

        qs = (
            Ticket.objects
            .select_related("user", "event", "event__organizer")
            .filter(user=self.request.user)
        )

        # ── Optional status filter ─────────────────────────────────────────
        if status_filter == "upcoming":
            qs = qs.filter(event__date__gt=now, is_scanned=False)
        elif status_filter == "past":
            qs = qs.filter(event__date__lte=now)
        elif status_filter == "used":
            qs = qs.filter(is_scanned=True)

        # ── Smart sort: upcoming first (ASC by date), then past (DESC) ─────
        # If client passes ?ordering= explicitly, skip smart sort
        if "ordering" not in self.request.query_params:
            qs = qs.annotate(
                _sort_group=Case(
                    When(event__date__gt=now, then=Value(0)),  # upcoming = group 0
                    default=Value(1),                           # past     = group 1
                    output_field=IntegerField(),
                )
            ).order_by("_sort_group", "event__date")

        return qs


class TicketScanView(APIView):
    """
    POST /api/tickets/<ticket_hash>/scan/

    Marks a ticket as scanned at the door.
    Permission: IsOrganizer — only authenticated Event Organizers.

    Body: {} (empty — ticket identified via URL hash)

    Responses:
      200 — {"status": "success",  "message": "Access granted",    "ticket": {...}}
      409 — {"status": "error",    "message": "Ticket already scanned", "scanned_at": "..."}
      403 — {"status": "error",    "message": "You are not authorized to scan this event"}
      404 — ticket hash not found
    """
    permission_classes = [IsOrganizer]

    def post(self, request, ticket_hash):
        ticket = get_object_or_404(
            Ticket.objects.select_related("user", "event", "event__organizer"),
            ticket_hash=ticket_hash,
        )

        # Organizer must own the event this ticket belongs to
        if ticket.event.organizer != request.user:
            return Response(
                {
                    "status": "error",
                    "message": "You are not authorized to scan this event.",
                    "event": ticket.event.title,
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        if ticket.is_scanned:
            return Response(
                {
                    "status": "error",
                    "message": "Ticket already scanned.",
                    "scanned_at": ticket.scanned_at,
                },
                status=status.HTTP_409_CONFLICT,
            )

        ticket.mark_scanned()
        output = TicketSerializer(ticket, context={"request": request})
        return Response(
            {
                "status": "success",
                "message": "Access granted.",
                "ticket": output.data,
            },
            status=status.HTTP_200_OK,
        )


class TicketVerifyView(APIView):
    """
    POST /api/tickets/verify/

    Accepts a ticket_hash in the request body, verifies the ticket,
    and marks it as scanned. Called by the QR code scanner page.

    Body: { "ticket_hash": "<64-char SHA-256 hash>" }
    Permission: IsOrganizer — only authenticated Event Organizers.

    Responses:
      200 — {"status": "success",  "message": "Access granted",           "ticket": {...}}
      409 — {"status": "error",    "message": "Ticket already scanned",   "scanned_at": "..."}
      403 — {"status": "error",    "message": "You are not authorized..."}
      404 — {"status": "error",    "message": "Ticket not found"}
      400 — {"status": "error",    "message": "ticket_hash is required"}
    """
    permission_classes = [IsOrganizer]

    def post(self, request):
        # ── Validate input ─────────────────────────────────────────────────
        ticket_hash = request.data.get("ticket_hash", "").strip()
        if not ticket_hash:
            return Response(
                {"status": "error", "message": "ticket_hash is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ── Fetch ticket (custom 404 message) ─────────────────────────────
        try:
            ticket = (
                Ticket.objects
                .select_related("user", "event", "event__organizer")
                .get(ticket_hash=ticket_hash)
            )
        except Ticket.DoesNotExist:
            return Response(
                {"status": "error", "message": "Ticket not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # ── Ownership check ────────────────────────────────────────────────
        if ticket.event.organizer != request.user:
            return Response(
                {
                    "status": "error",
                    "message": "You are not authorized to scan this event.",
                    "event": ticket.event.title,
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # ── Already scanned? ───────────────────────────────────────────────
        if ticket.is_scanned:
            return Response(
                {
                    "status": "error",
                    "message": "Ticket already scanned.",
                    "scanned_at": ticket.scanned_at,
                    "attendee": ticket.user.username,
                    "event": ticket.event.title,
                },
                status=status.HTTP_409_CONFLICT,
            )

        # ── Mark as scanned ────────────────────────────────────────────────
        ticket.mark_scanned()
        output = TicketSerializer(ticket, context={"request": request})
        return Response(
            {
                "status": "success",
                "message": "Access granted.",
                "ticket": output.data,
            },
            status=status.HTTP_200_OK,
        )


# --------------------------------------------------------------------------- #
# Like / Save Event Views
# --------------------------------------------------------------------------- #

class LikeEventToggleView(APIView):
    """
    POST   /api/events/<id>/like/  — like (save) an event
    DELETE /api/events/<id>/like/  — unlike (unsave) an event

    Acts as a toggle: POST is idempotent (liking twice is safe),
    DELETE returns 404 if the like does not exist.

    Auth: Bearer token required.

    POST Responses:
      201 — { "liked": true,  "likes_count": 42 }  (new like created)
      200 — { "liked": true,  "likes_count": 42 }  (already liked — idempotent)
      404 — event not found

    DELETE Responses:
      200 — { "liked": false, "likes_count": 41 }  (like removed)
      404 — like not found or event not found
    """
    permission_classes = [permissions.IsAuthenticated]

    def _get_event(self, event_id):
        return get_object_or_404(Event, pk=event_id, is_published=True)

    def post(self, request, event_id):
        """Like (save) an event. Idempotent — safe to call multiple times."""
        event = self._get_event(event_id)
        like, created = UserEventLike.objects.get_or_create(
            user=request.user,
            event=event,
        )
        likes_count = event.likes.count()
        return Response(
            {"liked": True, "likes_count": likes_count},
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    def delete(self, request, event_id):
        """Unlike (unsave) an event."""
        event = self._get_event(event_id)
        deleted, _ = UserEventLike.objects.filter(
            user=request.user, event=event
        ).delete()
        if not deleted:
            return Response(
                {"detail": "You have not liked this event."},
                status=status.HTTP_404_NOT_FOUND,
            )
        likes_count = event.likes.count()
        return Response(
            {"liked": False, "likes_count": likes_count},
            status=status.HTTP_200_OK,
        )


class UserLikedEventsView(generics.ListAPIView):
    """
    GET /api/user/liked-events/

    Returns all events that the currently authenticated user has liked/saved,
    ordered by most recently liked first.

    Each event is serialized with EventListSerializer (same shape as the
    public event list, including is_liked=True for every result).

    Supports:
      ?ordering=liked_at | event__date | event__title

    Auth: Bearer token required.
    """
    serializer_class   = EventListSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends    = [filters.OrderingFilter]
    ordering_fields    = ["liked_at", "event__date", "event__title"]
    ordering           = ["-liked_at"]

    def get_queryset(self):
        """
        Fetch the events the user has liked, annotated for tickets_remaining
        so the serializer doesn't need extra queries for that field either.
        """
        user = self.request.user
        return (
            Event.objects
            .select_related("organizer")
            .filter(likes__user=user, is_published=True)
            .annotate(
                _tickets_sold=Count("tickets"),
                _tickets_remaining=ExpressionWrapper(
                    F("total_tickets") - Count("tickets"),
                    output_field=IntegerField(),
                ),
                # liked_at for ordering support
                liked_at=F("likes__liked_at"),
            )
            .order_by("-liked_at")
        )

    def get_serializer_context(self):
        """
        Inject liked event IDs into serializer context.
        Since every event in this view IS liked by definition,
        we can pass all their PKs as a set for O(1) is_liked lookups.
        """
        ctx = super().get_serializer_context()
        # We know every event in this queryset is liked; pre-build the set
        # by re-using the queryset's PK values.
        qs = self.get_queryset()
        ctx["_user_likes_ids"] = set(qs.values_list("pk", flat=True))
        return ctx
