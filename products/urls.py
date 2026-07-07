from django.urls import path

from . import views

app_name = "products"

urlpatterns = [
    path("", views.CatalogView.as_view(), name="catalog"),
]
