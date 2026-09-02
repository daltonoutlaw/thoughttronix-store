import io
import secrets

import pyotp
import qrcode
import qrcode.image.svg
from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class User(AbstractUser):
    """The store's user model.

    Roles use Django's own vocabulary and nothing else: customers are
    plain users, employees are ``is_staff``, the admin is ``is_superuser``.
    """

    # Nullable per the PRD: an absent job title is unknown, not empty.
    job_title = models.CharField(max_length=150, null=True, blank=True)  # noqa: DJ001


class Address(models.Model):
    """A saved customer address for shipping and billing reuse."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="addresses",
    )
    label = models.CharField(max_length=100, blank=True)
    name = models.CharField(max_length=100)
    street = models.CharField(max_length=200)
    line2 = models.CharField(max_length=200, blank=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=2)
    zip = models.CharField(max_length=10)
    is_default_shipping = models.BooleanField(default=False)
    is_default_billing = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_default_shipping", "-is_default_billing", "-updated_at"]

    def __str__(self):
        label_part = f"{self.label}: " if self.label else ""
        return f"{label_part}{self.name}, {self.street}, {self.city}, {self.state} {self.zip}"

    def save(self, *args, **kwargs):
        # Auto-set as default if this is the user's first address
        if not self.pk and not self.user.addresses.exists():
            self.is_default_shipping = True
            self.is_default_billing = True

        if self.is_default_shipping and self.user_id:
            self.user.addresses.exclude(pk=self.pk).filter(
                is_default_shipping=True
            ).update(is_default_shipping=False)

        if self.is_default_billing and self.user_id:
            self.user.addresses.exclude(pk=self.pk).filter(
                is_default_billing=True
            ).update(is_default_billing=False)

        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        was_default_shipping = self.is_default_shipping
        was_default_billing = self.is_default_billing
        user = self.user
        pk = self.pk
        super().delete(*args, **kwargs)

        if was_default_shipping:
            fallback = user.addresses.exclude(pk=pk).order_by("-updated_at").first()
            if fallback and not fallback.is_default_shipping:
                fallback.is_default_shipping = True
                fallback.save(update_fields=["is_default_shipping"])

        if was_default_billing:
            fallback = user.addresses.exclude(pk=pk).order_by("-updated_at").first()
            if fallback and not fallback.is_default_billing:
                fallback.is_default_billing = True
                fallback.save(update_fields=["is_default_billing"])


class TOTPDevice(models.Model):
    """TOTP Two-Factor Authentication device configuration for a customer."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="totp_device",
    )
    secret_key = models.CharField(max_length=64, default=pyotp.random_base32)
    is_confirmed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        status = "confirmed" if self.is_confirmed else "unconfirmed"
        return f"TOTPDevice for {self.user.username} ({status})"

    def provisioning_uri(self, issuer_name="ThoughtTronix"):
        return pyotp.totp.TOTP(self.secret_key).provisioning_uri(
            name=self.user.username,
            issuer_name=issuer_name,
        )

    def qr_code_svg(self):
        """Generate inline SVG QR code for TOTP provisioning."""
        uri = self.provisioning_uri()
        factory = qrcode.image.svg.SvgPathImage
        img = qrcode.make(uri, image_factory=factory)
        stream = io.BytesIO()
        img.save(stream)
        return stream.getvalue().decode()

    def verify_code(self, code: str, valid_window: int = 1) -> bool:
        """Verify a 6-digit TOTP code against this secret key."""
        if not code or not code.strip().isdigit():
            return False
        totp = pyotp.TOTP(self.secret_key)
        if totp.verify(code.strip(), valid_window=valid_window):
            self.last_used_at = timezone.now()
            self.save(update_fields=["last_used_at"])
            return True
        return False


class BackupCode(models.Model):
    """Single-use backup recovery code for emergency 2FA account access."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="backup_codes",
    )
    code_hash = models.CharField(max_length=128)
    is_used = models.BooleanField(default=False)
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        status = "used" if self.is_used else "available"
        return f"BackupCode for {self.user.username} ({status})"

    @classmethod
    def generate_codes(cls, user, count: int = 8) -> list[str]:
        """Generate a fresh set of single-use backup recovery codes.

        Invalidates all previously existing backup codes for the user.
        Returns the plaintext codes list for one-time display.
        """
        cls.objects.filter(user=user).delete()
        raw_codes = []
        for _ in range(count):
            part1 = secrets.token_hex(2)
            part2 = secrets.token_hex(2)
            raw_code = f"{part1}-{part2}"
            raw_codes.append(raw_code)
            cls.objects.create(
                user=user,
                code_hash=make_password(raw_code),
            )
        return raw_codes

    @classmethod
    def verify_and_consume(cls, user, raw_code: str) -> bool:
        """Verify and consume a single-use backup recovery code.

        Returns True if code is valid and marks it used; otherwise False.
        """
        if not raw_code:
            return False
        cleaned_code = raw_code.strip()
        active_codes = cls.objects.filter(user=user, is_used=False)
        for backup_code in active_codes:
            if check_password(cleaned_code, backup_code.code_hash):
                backup_code.is_used = True
                backup_code.used_at = timezone.now()
                backup_code.save(update_fields=["is_used", "used_at"])
                return True
        return False


class UserSession(models.Model):
    """An active user session and connected device record."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sessions",
    )
    session_key = models.CharField(max_length=40, db_index=True)
    ip_address = models.CharField(max_length=45, blank=True)
    user_agent = models.TextField(blank=True)
    device_type = models.CharField(max_length=50, default="Desktop")
    last_activity = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-last_activity"]

    def __str__(self):
        return (
            f"Session for {self.user.username} ({self.device_type}, {self.ip_address})"
        )


class SecurityEvent(models.Model):
    """An audit log entry of security-critical actions and authentication attempts."""

    class EventType(models.TextChoices):
        LOGIN_SUCCESS = "LOGIN_SUCCESS", "Sign in successful"
        LOGIN_FAILED = "LOGIN_FAILED", "Failed sign-in attempt"
        PASSWORD_CHANGED = "PASSWORD_CHANGED", "Password changed"
        TWO_FACTOR_ENABLED = "TWO_FACTOR_ENABLED", "Two-factor authentication enabled"
        TWO_FACTOR_DISABLED = (
            "TWO_FACTOR_DISABLED",
            "Two-factor authentication disabled",
        )
        BACKUP_CODES_GENERATED = (
            "BACKUP_CODES_GENERATED",
            "Recovery codes regenerated",
        )
        BACKUP_CODE_USED = "BACKUP_CODE_USED", "Sign in using recovery code"
        SESSION_REVOKED = "SESSION_REVOKED", "Device session revoked"
        ALL_SESSIONS_REVOKED = (
            "ALL_SESSIONS_REVOKED",
            "All other sessions signed out",
        )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="security_events",
    )
    event_type = models.CharField(
        max_length=50,
        choices=EventType.choices,
        db_index=True,
    )
    ip_address = models.CharField(max_length=45, blank=True)
    device_type = models.CharField(max_length=50, default="Desktop")
    user_agent = models.TextField(blank=True)
    details = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_event_type_display()} for {self.user.username} at {self.created_at}"
