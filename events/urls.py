"""
events/urls.py
"""

from django.urls import path
from .views import (
    EventListCreateView,
    EventDetailView,
    OrganizerEventListView,
    EventAttendeesView,
    TicketPurchaseView,
    UserTicketListView,
    TicketScanView,
    TicketVerifyView,
)

urlpatterns = [
    # Public event endpoints
    path("events/",         EventListCreateView.as_view(), name="event-list-create"),
    path("events/<int:pk>/", EventDetailView.as_view(),    name="event-detail"),

    # Organizer-only dashboard endpoints
    path("organizer/events/",                              OrganizerEventListView.as_view(), name="organizer-event-list"),
    path("organizer/events/<int:event_id>/attendees/",     EventAttendeesView.as_view(),     name="organizer-event-attendees"),

    # Ticket endpoints
    path("tickets/purchase/",                  TicketPurchaseView.as_view(), name="ticket-purchase"),
    path("tickets/verify/",                    TicketVerifyView.as_view(),   name="ticket-verify"),
    path("tickets/<str:ticket_hash>/scan/",    TicketScanView.as_view(),     name="ticket-scan"),

    # Authenticated user's own tickets
    path("user/tickets/", UserTicketListView.as_view(), name="user-ticket-list"),
]
