from django.views.generic import ListView

from .models import Product


class CatalogView(ListView):
    """The public product catalog."""

    template_name = "products/catalog.html"
    context_object_name = "products"

    def get_queryset(self):
        return Product.objects.select_related("category")
