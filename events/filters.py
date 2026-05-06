"""
events/filters.py

django-filter FilterSet for the Event model.
Supports filtering by: category, date (exact / range), venue, price range.
"""

import django_filters
from .models import Event


class EventFilter(django_filters.FilterSet):
    """
    Enables the following query parameters on GET /api/events/:

        ?category=music
        ?date=2025-12-31
        ?date_after=2025-01-01&date_before=2025-12-31
        ?min_price=0&max_price=50
        ?venue=madison
        ?is_upcoming=true
    """

    # Category exact match (case-insensitive handled by TextChoices)
    category = django_filters.ChoiceFilter(choices=Event.Category.choices)

    # Exact date (date portion only)
    date = django_filters.DateFilter(field_name="date", lookup_expr="date")

    # Date range
    date_after = django_filters.DateFilter(
        field_name="date",
        lookup_expr="date__gte",
        label="Events on or after this date (YYYY-MM-DD)",
    )
    date_before = django_filters.DateFilter(
        field_name="date",
        lookup_expr="date__date__lte",
        label="Events on or before this date (YYYY-MM-DD)",
    )

    # Price range
    min_price = django_filters.NumberFilter(field_name="price", lookup_expr="gte")
    max_price = django_filters.NumberFilter(field_name="price", lookup_expr="lte")

    # Venue partial match
    venue = django_filters.CharFilter(
        field_name="venue_name",
        lookup_expr="icontains",
    )

    # Upcoming events only
    is_upcoming = django_filters.BooleanFilter(
        method="filter_upcoming",
        label="Show only upcoming events",
    )

    class Meta:
        model = Event
        fields = ["category", "date", "date_after", "date_before",
                  "min_price", "max_price", "venue", "is_upcoming"]

    def filter_upcoming(self, queryset, name, value):
        from django.utils import timezone
        if value:
            return queryset.filter(date__gte=timezone.now())
        return queryset.filter(date__lt=timezone.now())
