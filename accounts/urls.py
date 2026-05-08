"""
accounts/urls.py
"""

from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    CustomTokenObtainPairView,
    RegisterView,
    UserProfileView,
    LogoutView,
    IsOrganizerCheckView,
    PasswordResetRequestView,
    PasswordResetConfirmView,
)

urlpatterns = [
    # Auth
    path("register/",       RegisterView.as_view(),              name="auth-register"),
    path("token/",          CustomTokenObtainPairView.as_view(), name="auth-token-obtain"),
    path("token/refresh/",  TokenRefreshView.as_view(),          name="auth-token-refresh"),
    path("logout/",         LogoutView.as_view(),                name="auth-logout"),

    # Profile
    path("profile/",        UserProfileView.as_view(),           name="auth-profile"),
    path("is-organizer/",   IsOrganizerCheckView.as_view(),      name="auth-is-organizer"),

    # Password Reset (no auth required — user is logged out)
    path("password/reset/",         PasswordResetRequestView.as_view(), name="auth-password-reset"),
    path("password/reset/confirm/", PasswordResetConfirmView.as_view(), name="auth-password-reset-confirm"),
]
