"""Rate limiting utilities for authentication and 2FA challenge endpoints."""

from django.core.cache import cache


def get_client_ip(request) -> str:
    """Extract client IP address from request headers or remote addr."""
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "127.0.0.1")


def is_rate_limited(key: str, max_attempts: int = 5) -> bool:
    """Check whether a rate limit key has reached or exceeded max attempts."""
    attempts = cache.get(key, 0)
    return attempts >= max_attempts


def record_failure(key: str, timeout: int = 300) -> int:
    """Record a failed attempt and return the updated count."""
    attempts = cache.get(key, 0) + 1
    cache.set(key, attempts, timeout=timeout)
    return attempts


def clear_rate_limit(key: str) -> None:
    """Reset the failure counter for a rate limit key."""
    cache.delete(key)
