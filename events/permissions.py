"""
events/permissions.py

Custom DRF permission classes for the Event & Ticket platform.
"""

from rest_framework import permissions


class IsOrganizer(permissions.BasePermission):
    """
    Grants access only to authenticated users whose role is 'organizer'.

    Usage:
        permission_classes = [IsOrganizer]

    Responses:
        - 401 if not authenticated
        - 403 if authenticated but not an organizer
    """

    message = "Only Event Organizers are allowed to perform this action."

    def has_permission(self, request, view) -> bool:
        return (
            request.user
            and request.user.is_authenticated
            and request.user.is_organizer
        )


class IsOrganizerOrReadOnly(permissions.BasePermission):
    """
    Read-only access for everyone.
    Write access (POST/PUT/PATCH/DELETE) only for authenticated organizers.
    """

    def has_permission(self, request, view) -> bool:
        if request.method in permissions.SAFE_METHODS:
            return True
        return (
            request.user
            and request.user.is_authenticated
            and request.user.is_organizer
        )


class IsEventOwnerOrReadOnly(permissions.BasePermission):
    """
    Object-level: only the organizer who created the event can modify it.
    """

    def has_object_permission(self, request, view, obj) -> bool:
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.organizer == request.user
