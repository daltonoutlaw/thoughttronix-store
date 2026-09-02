from django.conf import settings
from django.db import models


class Wishlist(models.Model):
    """A customer's wishlist — one per user, created lazily on first touch."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="wishlist",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Wishlist for {self.user.username}"

    @classmethod
    def for_user(cls, user):
        """Return the user's wishlist, creating it on first touch."""
        wishlist, _ = cls.objects.get_or_create(user=user)
        return wishlist

    def contains(self, product):
        """Check whether a product is currently in the wishlist."""
        return self.items.filter(product=product).exists()

    def add(self, product):
        """Add a product to the wishlist if not already present."""
        item, _ = self.items.get_or_create(product=product)
        return item

    def remove(self, product):
        """Remove a product from the wishlist."""
        self.items.filter(product=product).delete()

    def toggle(self, product):
        """Toggle product in the wishlist; returns True if added, False if removed."""
        if self.contains(product):
            self.remove(product)
            return False
        self.add(product)
        return True


class WishlistItem(models.Model):
    """One product saved in a wishlist; the wishlist-product pair is unique."""

    wishlist = models.ForeignKey(
        Wishlist,
        on_delete=models.CASCADE,
        related_name="items",
    )
    product = models.ForeignKey(
        "products.Product",
        on_delete=models.CASCADE,
        related_name="wishlist_items",
    )
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-added_at", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["wishlist", "product"],
                name="unique_wishlist_product",
            )
        ]

    def __str__(self):
        return f"{self.product.name} in {self.wishlist}"
