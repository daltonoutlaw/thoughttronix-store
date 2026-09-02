from django.urls import path

from .views import WishlistDetailView, WishlistToggleView

app_name = "wishlists"

urlpatterns = [
    path("wishlist/", WishlistDetailView.as_view(), name="detail"),
    path("wishlist/toggle/<int:pk>/", WishlistToggleView.as_view(), name="toggle"),
]
