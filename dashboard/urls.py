from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("backoffice/dashboard/", views.DashboardView.as_view(), name="index"),
]
