"""Cart context for every page render.

``base.html`` shows the navbar cart badge on every page, and the catalog's
add-to-cart buttons show per-product quantities — one small query per
authenticated request supplies both.
"""

from .models import CartItem


def cart(request):
    if not request.user.is_authenticated:
        return {"cart_item_count": 0, "cart_quantities": {}}
    quantities = dict(
        CartItem.objects.filter(cart__user=request.user).values_list(
            "product_id", "quantity"
        )
    )
    return {
        "cart_item_count": sum(quantities.values()),
        "cart_quantities": quantities,
    }
