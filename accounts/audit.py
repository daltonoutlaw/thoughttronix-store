"""Audit logging and security transactional alert services."""

from django.conf import settings
from django.core.mail import send_mail

from .middleware import parse_device_type
from .models import SecurityEvent
from .rate_limit import get_client_ip


def record_security_event(
    user,
    event_type: str,
    request=None,
    details: str = "",
    send_alert: bool = False,
) -> SecurityEvent:
    """Log a security event and optionally send a transactional security alert."""
    if not user:
        return None

    ip = ""
    user_agent = ""
    device_type = "Desktop"

    if request:
        ip = get_client_ip(request)
        user_agent = request.META.get("HTTP_USER_AGENT", "")[:500]
        device_type = parse_device_type(user_agent)

    # Check for new device login alert
    is_new_device_login = False
    if event_type == SecurityEvent.EventType.LOGIN_SUCCESS:
        has_prior_login = SecurityEvent.objects.filter(
            user=user,
            event_type=SecurityEvent.EventType.LOGIN_SUCCESS,
            device_type=device_type,
        ).exists()
        if not has_prior_login:
            is_new_device_login = True

    event = SecurityEvent.objects.create(
        user=user,
        event_type=event_type,
        ip_address=ip,
        device_type=device_type,
        user_agent=user_agent,
        details=details,
    )

    from_email = (
        getattr(settings, "DEFAULT_FROM_EMAIL", "security@thoughttronix.example")
        or "security@thoughttronix.example"
    )

    # Send transactional alerts for critical security events
    if user.email:
        if event_type == SecurityEvent.EventType.PASSWORD_CHANGED:
            send_mail(
                subject="Security Alert: Password Changed",
                message=(
                    f"Hello {user.username},\n\n"
                    "Your ThoughtTronix account password was changed successfully.\n"
                    f"Device: {device_type}\n"
                    f"IP Address: {ip or 'Unknown'}\n\n"
                    "If you did not perform this change, please contact our security team immediately.\n\n"
                    "— The ThoughtTronix Security Team"
                ),
                from_email=from_email,
                recipient_list=[user.email],
                fail_silently=False,
            )
        elif event_type == SecurityEvent.EventType.TWO_FACTOR_ENABLED:
            send_mail(
                subject="Security Alert: Two-factor authentication enabled",
                message=(
                    f"Hello {user.username},\n\n"
                    "Two-factor authentication has been successfully enabled on your account.\n"
                    f"Device: {device_type}\n"
                    f"IP Address: {ip or 'Unknown'}\n\n"
                    "If you did not perform this setup, please secure your account immediately.\n\n"
                    "— The ThoughtTronix Security Team"
                ),
                from_email=from_email,
                recipient_list=[user.email],
                fail_silently=True,
            )
        elif event_type == SecurityEvent.EventType.TWO_FACTOR_DISABLED:
            send_mail(
                subject="Security Alert: Two-factor authentication was disabled",
                message=(
                    f"Hello {user.username},\n\n"
                    "Two-factor authentication was just disabled on your account.\n"
                    f"Device: {device_type}\n"
                    f"IP Address: {ip or 'Unknown'}\n\n"
                    "If you did not authorize this change, please log into your account and change your password immediately.\n\n"
                    "— The ThoughtTronix Security Team"
                ),
                from_email=from_email,
                recipient_list=[user.email],
                fail_silently=True,
            )
        elif is_new_device_login or send_alert:
            send_mail(
                subject="Security Alert: New sign-in to your ThoughtTronix account",
                message=(
                    f"Hello {user.username},\n\n"
                    f"A new sign-in was detected for your account from {device_type} (IP: {ip or 'Unknown'}).\n\n"
                    "If this was you, you can safely ignore this message. If you do not recognize this activity, "
                    "please visit your Security Center to review active sessions and change your password.\n\n"
                    "— The ThoughtTronix Security Team"
                ),
                from_email=from_email,
                recipient_list=[user.email],
                fail_silently=True,
            )

    return event
