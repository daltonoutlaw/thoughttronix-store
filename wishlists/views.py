from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, render
from django.views import View

from products.models import Product

from .models import Wishlist


class WishlistDetailView(LoginRequiredMixin, View):
    """Render the signed-in customer's wishlist items in reverse chronological order."""

    def get(self, request):
        wishlist = Wishlist.for_user(request.user)
        items = wishlist.items.select_related("product", "product__category").order_by(
            "-added_at"
        )
        return render(
            request,
            "wishlists/detail.html",
            {"wishlist": wishlist, "items": items},
        )


class WishlistToggleView(LoginRequiredMixin, View):
    """HTMX: toggle a product in the customer's wishlist; swaps the button in place."""

    def post(self, request, pk):
        product = get_object_or_404(Product, pk=pk)
        wishlist = Wishlist.for_user(request.user)
        in_wishlist = wishlist.toggle(product)
        return render(
            request,
            "wishlists/partials/_toggle_button.html",
            {"product": product, "in_wishlist": in_wishlist},
        )
