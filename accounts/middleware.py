"""Middleware for tracking active user sessions and devices."""

from datetime import timedelta

from django.contrib.auth import logout as auth_logout
from django.utils import timezone

from .models import UserSession
from .rate_limit import get_client_ip


def parse_device_type(user_agent: str) -> str:
    """Parse a User-Agent string into a readable device and platform label."""
    if not user_agent:
        return "Unknown Device"
    ua = user_agent.lower()

    if "ipad" in ua or "tablet" in ua:
        category = "Tablet"
    elif "mobi" in ua or "iphone" in ua or "android" in ua:
        category = "Mobile"
    else:
        category = "Desktop"

    if "ipad" in ua:
        platform = "iPadOS"
    elif "iphone" in ua:
        platform = "iOS"
    elif "android" in ua:
        platform = "Android"
    elif "macintosh" in ua or "mac os" in ua:
        platform = "macOS"
    elif "windows" in ua:
        platform = "Windows"
    elif "linux" in ua:
        platform = "Linux"
    else:
        platform = ""

    if platform:
        return f"{category} ({platform})"
    return category


class UserSessionMiddleware:
    """Track active user sessions, update activity timestamps, and enforce 30-day lifetime."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and request.session.session_key:
            now = timezone.now()
            cutoff = now - timedelta(days=30)

            # Check if current session has expired (30-day lifetime)
            existing_session = UserSession.objects.filter(
                user=request.user, session_key=request.session.session_key
            ).first()

            if existing_session and existing_session.last_activity < cutoff:
                existing_session.delete()
                auth_logout(request)
            else:
                user_agent_str = request.META.get("HTTP_USER_AGENT", "")
                device_type = parse_device_type(user_agent_str)
                ip = get_client_ip(request)

                UserSession.objects.update_or_create(
                    user=request.user,
                    session_key=request.session.session_key,
                    defaults={
                        "ip_address": ip,
                        "user_agent": user_agent_str[:500],
                        "device_type": device_type,
                        "last_activity": now,
                    },
                )

        response = self.get_response(request)
        return response
