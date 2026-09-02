from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("signup/", views.SignupView.as_view(), name="signup"),
    path("login/", views.SignInView.as_view(), name="login"),
    path(
        "login/2fa/",
        views.TwoFactorChallengeView.as_view(),
        name="two_factor_challenge",
    ),
    path("logout/", views.SignOutView.as_view(), name="logout"),
    path("security/", views.SecurityCenterView.as_view(), name="security_center"),
    path(
        "security/password/",
        views.PasswordChangeView.as_view(),
        name="password_change",
    ),
    path(
        "security/2fa/setup/",
        views.TwoFactorSetupView.as_view(),
        name="two_factor_setup",
    ),
    path(
        "security/2fa/verify/",
        views.TwoFactorVerifyView.as_view(),
        name="two_factor_verify",
    ),
    path(
        "security/2fa/backup-codes/",
        views.TwoFactorBackupCodesView.as_view(),
        name="two_factor_backup_codes",
    ),
    path(
        "security/2fa/disable/",
        views.TwoFactorDisableView.as_view(),
        name="two_factor_disable",
    ),
    path(
        "security/sessions/",
        views.SessionListView.as_view(),
        name="session_list",
    ),
    path(
        "security/sessions/<int:pk>/revoke/",
        views.SessionRevokeView.as_view(),
        name="session_revoke",
    ),
    path(
        "security/sessions/revoke-others/",
        views.SessionRevokeOthersView.as_view(),
        name="session_revoke_others",
    ),
    path(
        "security/activity/",
        views.SecurityActivityView.as_view(),
        name="security_activity",
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
