from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models


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
