from django.urls import path

from . import views

app_name = "products"

urlpatterns = [
    path("", views.CatalogView.as_view(), name="catalog"),
    path("products/<slug:slug>/", views.ProductDetailView.as_view(), name="detail"),
    path("categories/<slug:slug>/", views.CategoryView.as_view(), name="category"),
]
