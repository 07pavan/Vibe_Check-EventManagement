"""
core/urls.py — Root URL configuration
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    # Django admin
    path("admin/", admin.site.urls),

    # Auth endpoints  →  /api/auth/register/, /api/auth/token/, etc.
    path("api/auth/", include("accounts.urls")),

    # Events & Tickets  →  /api/events/, /api/tickets/purchase/, /api/user/tickets/
    path("api/", include("events.urls")),
]

# Serve uploaded media files during development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
