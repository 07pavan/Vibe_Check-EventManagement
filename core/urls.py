"""
core/urls.py — Root URL configuration
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.http import JsonResponse


def health_check(request):
    """
    GET /health/
    Render uses this endpoint to verify the service is alive.
    Returns 200 immediately — no DB query, no auth, no overhead.
    WHY: Without a health check, Render marks deploys as failed even
    when the app is running fine. Keep this response < 1KB and < 100ms.
    """
    return JsonResponse({"status": "ok"})


urlpatterns = [
    # Render health check — must be fast and unauthenticated
    path("health/", health_check, name="health-check"),

    # Django admin
    path("admin/", admin.site.urls),

    # Auth endpoints  →  /api/auth/register/, /api/auth/token/, etc.
    path("api/auth/", include("accounts.urls")),

    # Events & Tickets  →  /api/events/, /api/tickets/purchase/, /api/user/tickets/
    path("api/", include("events.urls")),
]

# Serve uploaded media files during development only.
# In production, Cloudinary handles media — this block is a no-op.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
