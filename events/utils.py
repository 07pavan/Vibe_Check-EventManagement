"""
events/utils.py

Shared utility functions for the GoAttend backend.

Image URL helpers
-----------------
`build_image_urls(obj, field_name, request)` builds an absolute-URL dict
for the original image plus all generated size variants.

Usage in serializers:
    from .utils import build_image_urls

    def get_images(self, obj):
        return build_image_urls(obj, "image", self.context.get("request"))
"""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from django.http import HttpRequest


# Names of the ImageSpecField variants that may exist on the model.
# The helper silently skips any name that isn't present on the instance.
_SPEC_VARIANTS = ("image_thumbnail", "image_medium", "image_large")
_AVATAR_VARIANTS = ("avatar_thumbnail", "avatar_medium")


def _safe_spec_url(spec_field, request: "HttpRequest | None") -> str | None:
    """
    Safely retrieve the URL of a django-imagekit ImageSpecField.

    Returns None if:
      - the source image is not set / empty
      - the cache file hasn't been generated yet and generation fails
    """
    try:
        url = spec_field.url
        if request:
            return request.build_absolute_uri(url)
        return url
    except Exception:
        return None


def build_image_urls(obj, source_field: str, request: "HttpRequest | None") -> dict:
    """
    Returns a dict of all image URL variants for *obj*.

    Example return value:
        {
            "original":  "http://localhost:8000/media/events/images/banner.jpg",
            "thumbnail": "http://localhost:8000/media/CACHE/images/events/images/banner/thumbnail.jpg",
            "medium":    "http://localhost:8000/media/CACHE/images/events/images/banner/medium.jpg",
            "large":     "http://localhost:8000/media/CACHE/images/events/images/banner/large.jpg"
        }

    Any key whose image could not be generated is set to None.

    Args:
        obj:          Model instance (Event or User)
        source_field: Name of the source ImageField ('image' or 'avatar')
        request:      DRF request (used to build absolute URLs); None for relative.
    """
    source = getattr(obj, source_field, None)
    if not source:
        # No image uploaded — all variants are None
        return {k: None for k in ("original", "thumbnail", "medium", "large")}

    # Original image absolute URL
    try:
        original_url = request.build_absolute_uri(source.url) if request else source.url
    except Exception:
        original_url = None

    result: dict = {"original": original_url}

    # Determine which spec variants to look for based on source field name
    if source_field == "avatar":
        spec_map = {"thumbnail": "avatar_thumbnail", "medium": "avatar_medium"}
    else:
        spec_map = {
            "thumbnail": "image_thumbnail",
            "medium":    "image_medium",
            "large":     "image_large",
        }

    for size_label, attr_name in spec_map.items():
        spec = getattr(obj, attr_name, None)
        result[size_label] = _safe_spec_url(spec, request) if spec else None

    return result


def get_device(request) -> str:
    """
    Reads the `?device=` query parameter from the request and normalises it.
    Falls back to 'desktop' when absent or unrecognised.
    """
    VALID = {"mobile", "tablet", "desktop"}
    raw = getattr(request, "query_params", {}).get("device", "desktop")
    return raw.lower() if raw.lower() in VALID else "desktop"
