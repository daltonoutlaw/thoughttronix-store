from django import template

register = template.Library()


@register.filter
def quantity_of(cart_quantities, product_pk):
    """Look up a product's cart quantity from the context processor's dict."""
    return cart_quantities.get(product_pk, 0)
