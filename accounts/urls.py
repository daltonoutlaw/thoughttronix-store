from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("signup/", views.SignupView.as_view(), name="signup"),
    path("login/", views.SignInView.as_view(), name="login"),
    path("logout/", views.SignOutView.as_view(), name="logout"),
    path("security/", views.SecurityCenterView.as_view(), name="security_center"),
    path(
        "security/password/",
        views.PasswordChangeView.as_view(),
        name="password_change",
    ),
    path("addresses/", views.AddressListView.as_view(), name="address_list"),
    path("addresses/add/", views.AddressCreateView.as_view(), name="address_create"),
    path(
        "addresses/<int:pk>/edit/",
        views.AddressUpdateView.as_view(),
        name="address_update",
    ),
    path(
        "addresses/<int:pk>/delete/",
        views.AddressDeleteView.as_view(),
        name="address_delete",
    ),
    path(
        "addresses/<int:pk>/set-default/",
        views.SetDefaultAddressView.as_view(),
        name="address_set_default",
    ),
]
