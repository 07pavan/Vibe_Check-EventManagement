"""
events/pagination.py

Device-aware pagination for the GoAttend API.

The page size is automatically scaled based on the optional `?device=`
query parameter sent by the frontend:

    ?device=mobile   →  10 items per page  (fast load, small screen)
    ?device=tablet   →  15 items per page
    ?device=desktop  →  20 items per page  (default when param is absent)

The frontend can also override page size explicitly with ?page_size=N
(capped at PAGE_SIZE_MAX to prevent abuse).
"""

from rest_framework.pagination import PageNumberPagination


# Caps to prevent a client from requesting the entire table in one shot
PAGE_SIZE_MAX = 100


class DeviceAwarePagination(PageNumberPagination):
    """
    PageNumberPagination subclass that adjusts the page size based on the
    `device` query parameter.  Supports standard `?page=N` navigation.

    Response envelope:
        {
            "count":    <total items>,
            "next":     <URL | null>,
            "previous": <URL | null>,
            "device":   "mobile" | "tablet" | "desktop",
            "page_size": <int>,
            "results":  [...]
        }
    """

    page_size = 20                        # desktop default
    page_size_query_param = "page_size"   # allow explicit override
    max_page_size = PAGE_SIZE_MAX

    # Page-size presets per device type
    _DEVICE_SIZES: dict[str, int] = {
        "mobile":  10,
        "tablet":  15,
        "desktop": 20,
    }

    def get_page_size(self, request) -> int:
        # If the client passed an explicit ?page_size=N, respect it (up to max)
        explicit = request.query_params.get(self.page_size_query_param)
        if explicit:
            try:
                size = int(explicit)
                return min(max(size, 1), PAGE_SIZE_MAX)
            except (ValueError, TypeError):
                pass

        device = request.query_params.get("device", "desktop").lower()
        return self._DEVICE_SIZES.get(device, self._DEVICE_SIZES["desktop"])

    def get_paginated_response(self, data):
        """
        Extends the default envelope with `device` and `page_size` fields
        so the frontend knows which preset was applied.
        """
        from rest_framework.response import Response

        request = self.request
        device = request.query_params.get("device", "desktop").lower()
        if device not in self._DEVICE_SIZES:
            device = "desktop"

        return Response({
            "count":     self.page.paginator.count,
            "next":      self.get_next_link(),
            "previous":  self.get_previous_link(),
            "device":    device,
            "page_size": self.get_page_size(request),
            "results":   data,
        })
