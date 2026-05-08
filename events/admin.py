"""
events/admin.py
"""

from django.contrib import admin
from .models import Event, Ticket, UserEventLike


class TicketInline(admin.TabularInline):
    """Show tickets sold directly on the Event admin page."""
    model = Ticket
    extra = 0
    readonly_fields = ("user", "ticket_hash", "is_scanned", "scanned_at", "purchased_at", "price_paid")
    can_delete = False


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = (
        "title", "category", "date", "venue_name",
        "price", "organizer", "tickets_sold", "is_published",
    )
    list_filter = ("category", "is_published", "date")
    search_fields = ("title", "venue_name", "organizer__username")
    ordering = ("date",)
    readonly_fields = ("created_at", "updated_at")
    inlines = [TicketInline]

    def tickets_sold(self, obj):
        return obj.tickets_sold
    tickets_sold.short_description = "Sold"


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = (
        "id", "user", "event", "is_scanned",
        "scanned_at", "purchased_at", "price_paid",
    )
    list_filter = ("is_scanned", "event__category")
    search_fields = ("user__username", "event__title", "ticket_hash")
    readonly_fields = ("ticket_hash", "purchased_at", "scanned_at")
    ordering = ("-purchased_at",)


@admin.register(UserEventLike)
class UserEventLikeAdmin(admin.ModelAdmin):
    list_display = ("user", "event", "liked_at")
    list_filter = ("event__category",)
    search_fields = ("user__username", "event__title")
    ordering = ("-liked_at",)

