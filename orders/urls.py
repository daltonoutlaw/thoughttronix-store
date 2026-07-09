from django.urls import path

from . import views

app_name = "orders"

urlpatterns = [
    path("cart/", views.CartView.as_view(), name="cart"),
    path("cart/add/<int:pk>/", views.AddToCartView.as_view(), name="add"),
    path(
        "cart/items/<int:pk>/increment/",
        views.IncrementCartItemView.as_view(),
        name="increment",
    ),
    path(
        "cart/items/<int:pk>/decrement/",
        views.DecrementCartItemView.as_view(),
        name="decrement",
    ),
    path(
        "cart/items/<int:pk>/remove/",
        views.RemoveCartItemView.as_view(),
        name="remove",
    ),
]
