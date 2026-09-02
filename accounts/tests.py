from datetime import timedelta
from http import HTTPStatus
from importlib import import_module

import pyotp
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.urls import reverse
from django.utils import timezone

from .middleware import parse_device_type
from .models import (
    Address,
    BackupCode,
    SecurityEvent,
    TOTPDevice,
    UserSession,
)

# --- Signup -----------------------------------------------------------------


def test_signup_page_returns_200(client, db):
    response = client.get(reverse("accounts:signup"))

    assert response.status_code == HTTPStatus.OK


def test_signup_creates_plain_customer(client, db):
    response = client.post(
        reverse("accounts:signup"),
        {
            "username": "fresh-thinker",
            "password1": "neural-implant-9000",
            "password2": "neural-implant-9000",
        },
        follow=True,
    )

    user = get_user_model().objects.get(username="fresh-thinker")
    assert not user.is_staff
    assert not user.is_superuser

    # Signup hands off to the login page with a confirmation message;
    # auto-login is a student exercise, so the visitor is still anonymous.
    assert response.redirect_chain[-1][0] == reverse("accounts:login")
    assert "Account created" in response.content.decode()
    assert not response.context["user"].is_authenticated


def test_signup_password_mismatch_shows_field_error(client, db):
    response = client.post(
        reverse("accounts:signup"),
        {
            "username": "fresh-thinker",
            "password1": "neural-implant-9000",
            "password2": "neural-implant-9001",
        },
    )

    assert response.status_code == HTTPStatus.OK
    assert response.context["form"].errors["password2"]
    assert not get_user_model().objects.filter(username="fresh-thinker").exists()


# --- Login and logout --------------------------------------------------------


def test_login_page_returns_200(client, db):
    response = client.get(reverse("accounts:login"))

    assert response.status_code == HTTPStatus.OK


def test_login_round_trip(client, customer):
    response = client.post(
        reverse("accounts:login"),
        {"username": "customer", "password": "customer123"},
        follow=True,
    )

    assert response.redirect_chain[-1][0] == reverse("products:catalog")
    assert response.context["user"] == customer


def test_login_bad_credentials_stays_put(client, customer):
    response = client.post(
        reverse("accounts:login"),
        {"username": "customer", "password": "wrong"},
    )

    assert response.status_code == HTTPStatus.OK
    assert response.context["form"].non_field_errors()


def test_logout_signs_out_with_message(client, customer):
    client.force_login(customer)

    response = client.post(reverse("accounts:logout"), follow=True)

    assert response.redirect_chain[-1][0] == reverse("products:catalog")
    assert "You have signed out." in response.content.decode()
    assert not response.context["user"].is_authenticated


# --- Auth-aware navbar --------------------------------------------------------


def test_navbar_offers_login_and_signup_to_visitors(client, db):
    page = client.get(reverse("products:catalog")).content.decode()

    assert reverse("accounts:login") in page
    assert reverse("accounts:signup") in page
    assert "Sign out" not in page


def test_navbar_greets_signed_in_customer(client, customer):
    client.force_login(customer)

    page = client.get(reverse("products:catalog")).content.decode()

    assert "Hi, customer" in page
    assert "Sign out" in page
    assert reverse("accounts:address_list") in page
    assert reverse("accounts:security_center") in page
    assert "Security Center" in page
    assert reverse("accounts:signup") not in page


# --- Address model and management --------------------------------------------


def test_first_address_auto_defaults_shipping_and_billing(customer):
    addr = Address.objects.create(
        user=customer,
        name="Casey Monroe",
        street="12 Cortex Lane",
        city="Canyon",
        state="TX",
        zip="79015",
    )
    assert addr.is_default_shipping
    assert addr.is_default_billing


def test_setting_default_unsets_previous_default(customer):
    addr1 = Address.objects.create(
        user=customer,
        name="Casey Monroe",
        street="12 Cortex Lane",
        city="Canyon",
        state="TX",
        zip="79015",
    )
    addr2 = Address.objects.create(
        user=customer,
        name="Casey Monroe",
        street="45 Synapse Blvd",
        city="Canyon",
        state="TX",
        zip="79015",
        is_default_shipping=True,
    )
    addr1.refresh_from_db()
    assert not addr1.is_default_shipping
    assert addr1.is_default_billing  # billing default unchanged
    assert addr2.is_default_shipping


def test_deleting_default_falls_back_to_remaining_address(customer):
    addr1 = Address.objects.create(
        user=customer,
        name="Casey Monroe",
        street="12 Cortex Lane",
        city="Canyon",
        state="TX",
        zip="79015",
    )
    addr2 = Address.objects.create(
        user=customer,
        name="Casey Monroe",
        street="45 Synapse Blvd",
        city="Canyon",
        state="TX",
        zip="79015",
        is_default_shipping=True,
        is_default_billing=True,
    )
    addr2.delete()
    addr1.refresh_from_db()
    assert addr1.is_default_shipping
    assert addr1.is_default_billing


def test_address_str_formatting(customer):
    addr_labeled = Address(
        user=customer,
        label="Home",
        name="Casey Monroe",
        street="12 Cortex Lane",
        city="Canyon",
        state="TX",
        zip="79015",
    )
    assert str(addr_labeled) == "Home: Casey Monroe, 12 Cortex Lane, Canyon, TX 79015"

    addr_unlabeled = Address(
        user=customer,
        name="Casey Monroe",
        street="12 Cortex Lane",
        city="Canyon",
        state="TX",
        zip="79015",
    )
    assert str(addr_unlabeled) == "Casey Monroe, 12 Cortex Lane, Canyon, TX 79015"


def test_address_list_requires_login(client, db):
    response = client.get(reverse("accounts:address_list"))
    assert response.status_code == HTTPStatus.FOUND
    assert reverse("accounts:login") in response.url


def test_address_list_shows_only_customer_addresses(client, customer, db):
    other = get_user_model().objects.create_user(username="other", password="x")
    Address.objects.create(
        user=customer,
        label="Casey Home",
        name="Casey Monroe",
        street="12 Cortex Lane",
        city="Canyon",
        state="TX",
        zip="79015",
    )
    Address.objects.create(
        user=other,
        label="Other Secret HQ",
        name="Other User",
        street="99 Hidden Rd",
        city="Canyon",
        state="TX",
        zip="79015",
    )

    client.force_login(customer)
    response = client.get(reverse("accounts:address_list"))

    assert response.status_code == HTTPStatus.OK
    content = response.content.decode()
    assert "Casey Home" in content
    assert "Other Secret HQ" not in content


def test_address_create_view(client, customer):
    client.force_login(customer)
    response = client.post(
        reverse("accounts:address_create"),
        {
            "label": "Office",
            "name": "Casey Monroe",
            "street": "100 Tech Way",
            "line2": "Suite 400",
            "city": "Austin",
            "state": "TX",
            "zip": "78701",
        },
        follow=True,
    )
    assert response.redirect_chain[-1][0] == reverse("accounts:address_list")
    assert Address.objects.filter(user=customer, label="Office").exists()


def test_address_update_view(client, customer):
    addr = Address.objects.create(
        user=customer,
        label="Old Label",
        name="Casey Monroe",
        street="12 Cortex Lane",
        city="Canyon",
        state="TX",
        zip="79015",
    )
    client.force_login(customer)
    response = client.post(
        reverse("accounts:address_update", kwargs={"pk": addr.pk}),
        {
            "label": "New Label",
            "name": "Casey Monroe",
            "street": "12 Cortex Lane",
            "line2": "",
            "city": "Canyon",
            "state": "TX",
            "zip": "79015",
        },
        follow=True,
    )
    assert response.redirect_chain[-1][0] == reverse("accounts:address_list")
    addr.refresh_from_db()
    assert addr.label == "New Label"


def test_address_update_forbidden_for_other_user(client, customer, db):
    other = get_user_model().objects.create_user(username="other", password="x")
    other_addr = Address.objects.create(
        user=other,
        name="Other User",
        street="99 Hidden Rd",
        city="Canyon",
        state="TX",
        zip="79015",
    )
    client.force_login(customer)
    response = client.get(
        reverse("accounts:address_update", kwargs={"pk": other_addr.pk})
    )
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_address_delete_view(client, customer):
    addr = Address.objects.create(
        user=customer,
        name="Casey Monroe",
        street="12 Cortex Lane",
        city="Canyon",
        state="TX",
        zip="79015",
    )
    client.force_login(customer)
    response = client.post(
        reverse("accounts:address_delete", kwargs={"pk": addr.pk}), follow=True
    )
    assert response.redirect_chain[-1][0] == reverse("accounts:address_list")
    assert not Address.objects.filter(pk=addr.pk).exists()


def test_set_default_address_view(client, customer):
    addr1 = Address.objects.create(
        user=customer,
        name="Casey Monroe",
        street="12 Cortex Lane",
        city="Canyon",
        state="TX",
        zip="79015",
    )
    addr2 = Address.objects.create(
        user=customer,
        name="Casey Monroe",
        street="45 Synapse Blvd",
        city="Canyon",
        state="TX",
        zip="79015",
    )
    client.force_login(customer)
    client.post(
        reverse("accounts:address_set_default", kwargs={"pk": addr2.pk}),
        {"target": "shipping"},
    )
    addr1.refresh_from_db()
    addr2.refresh_from_db()
    assert not addr1.is_default_shipping
    assert addr2.is_default_shipping


# --- Security Center & Password Rotation (Phase 1) --------------------------


def test_security_center_requires_login(client, db):
    response = client.get(reverse("accounts:security_center"))
    assert response.status_code == HTTPStatus.FOUND
    assert reverse("accounts:login") in response.url


def test_security_center_renders_posture_cards_for_authenticated_customer(
    client, customer
):
    client.force_login(customer)
    response = client.get(reverse("accounts:security_center"))

    assert response.status_code == HTTPStatus.OK
    content = response.content.decode()
    assert "Account Security Center" in content
    assert "Password Protection" in content
    assert "Two-Factor Auth" in content
    assert "Active Sessions" in content
    assert reverse("accounts:password_change") in content


def test_password_change_requires_login(client, db):
    response = client.get(reverse("accounts:password_change"))
    assert response.status_code == HTTPStatus.FOUND
    assert reverse("accounts:login") in response.url


def test_password_change_page_returns_200(client, customer):
    client.force_login(customer)
    response = client.get(reverse("accounts:password_change"))

    assert response.status_code == HTTPStatus.OK
    assert "Change Password" in response.content.decode()
    assert "form" in response.context


def test_password_change_invalid_current_password(client, customer):
    client.force_login(customer)
    response = client.post(
        reverse("accounts:password_change"),
        {
            "old_password": "wrongpassword",
            "new_password1": "SecureNewPass999!",
            "new_password2": "SecureNewPass999!",
        },
    )

    assert response.status_code == HTTPStatus.OK
    assert response.context["form"].errors["old_password"]

    # Verify password was not altered
    customer.refresh_from_db()
    assert customer.check_password("customer123")
    assert not customer.check_password("SecureNewPass999!")


def test_password_change_mismatched_new_passwords(client, customer):
    client.force_login(customer)
    response = client.post(
        reverse("accounts:password_change"),
        {
            "old_password": "customer123",
            "new_password1": "SecureNewPass999!",
            "new_password2": "DifferentPass888!",
        },
    )

    assert response.status_code == HTTPStatus.OK
    assert response.context["form"].errors["new_password2"]

    customer.refresh_from_db()
    assert customer.check_password("customer123")


def test_password_change_too_weak(client, customer):
    client.force_login(customer)
    response = client.post(
        reverse("accounts:password_change"),
        {
            "old_password": "customer123",
            "new_password1": "123",
            "new_password2": "123",
        },
    )

    assert response.status_code == HTTPStatus.OK
    assert response.context["form"].errors["new_password2"]

    customer.refresh_from_db()
    assert customer.check_password("customer123")


def test_password_change_successful_rotation_and_email(client, customer):
    customer.email = "casey@thoughttronix.com"
    customer.save()

    client.force_login(customer)
    response = client.post(
        reverse("accounts:password_change"),
        {
            "old_password": "customer123",
            "new_password1": "SecureNewPass999!",
            "new_password2": "SecureNewPass999!",
        },
        follow=True,
    )

    # Verifies redirect to Security Center and success notification
    assert response.redirect_chain[-1][0] == reverse("accounts:security_center")
    assert "Your password has been changed successfully." in response.content.decode()

    # Verifies session is kept active without unexpected sign-out
    assert response.context["user"].is_authenticated
    assert response.context["user"] == customer

    # Verifies database password hash was updated
    customer.refresh_from_db()
    assert customer.check_password("SecureNewPass999!")
    assert not customer.check_password("customer123")

    # Verifies transactional alert email was dispatched
    assert len(mail.outbox) == 1
    email = mail.outbox[0]
    assert email.to == ["casey@thoughttronix.com"]
    assert "Security Alert: Password Changed" in email.subject
    assert "changed successfully" in email.body


# --- TOTP Two-Factor Authentication & Recovery Codes (Phase 2) --------------


def test_totp_device_model_qr_generation_and_verification(customer):
    device = TOTPDevice.objects.create(user=customer)
    assert device.secret_key
    assert not device.is_confirmed

    uri = device.provisioning_uri()
    assert uri.startswith("otpauth://totp/ThoughtTronix:customer?")
    assert f"secret={device.secret_key}" in uri

    qr_svg = device.qr_code_svg()
    assert "<svg" in qr_svg
    assert "</svg>" in qr_svg

    # Valid time-step verification
    totp = pyotp.TOTP(device.secret_key)
    current_code = totp.now()
    assert device.verify_code(current_code)
    device.refresh_from_db()
    assert device.last_used_at is not None

    # Invalid code
    assert not device.verify_code("000000")
    assert not device.verify_code("abc")
    assert not device.verify_code("")


def test_backup_codes_model_generation_and_consumption(customer):
    raw_codes = BackupCode.generate_codes(customer, count=8)
    assert len(raw_codes) == 8
    assert customer.backup_codes.count() == 8

    # Verify codes are stored as hashes, not plaintext
    first_code = raw_codes[0]
    assert not customer.backup_codes.filter(code_hash=first_code).exists()
    assert customer.backup_codes.filter(is_used=False).count() == 8

    # Consume the first code
    assert BackupCode.verify_and_consume(customer, first_code)
    assert customer.backup_codes.filter(is_used=False).count() == 7
    assert customer.backup_codes.filter(is_used=True).count() == 1

    # Consuming the same code again fails (single-use enforcement)
    assert not BackupCode.verify_and_consume(customer, first_code)

    # Consuming an invalid code fails
    assert not BackupCode.verify_and_consume(customer, "invalid-code")


def test_two_factor_setup_requires_login(client, db):
    response = client.get(reverse("accounts:two_factor_setup"))
    assert response.status_code == HTTPStatus.FOUND
    assert reverse("accounts:login") in response.url


def test_two_factor_setup_renders_qr_and_secret_key(client, customer):
    client.force_login(customer)
    response = client.get(reverse("accounts:two_factor_setup"))

    assert response.status_code == HTTPStatus.OK
    content = response.content.decode()
    assert "Set Up Two-Factor Authentication" in content
    assert "<svg" in content
    assert "Verify & Activate 2FA" in content

    # Verify an unconfirmed TOTP device was created
    device = TOTPDevice.objects.get(user=customer)
    assert not device.is_confirmed


def test_two_factor_setup_redirects_if_already_enabled(client, customer):
    TOTPDevice.objects.create(user=customer, is_confirmed=True)
    client.force_login(customer)

    response = client.get(reverse("accounts:two_factor_setup"))
    assert response.status_code == HTTPStatus.FOUND
    assert response.url == reverse("accounts:two_factor_backup_codes")


def test_two_factor_verify_invalid_code_shows_error(client, customer):
    TOTPDevice.objects.create(user=customer, is_confirmed=False)
    client.force_login(customer)

    response = client.post(
        reverse("accounts:two_factor_verify"),
        {"code": "000000"},
    )

    assert response.status_code == HTTPStatus.OK
    assert response.context["form"].errors["code"]
    device = TOTPDevice.objects.get(user=customer)
    assert not device.is_confirmed


def test_two_factor_verify_valid_code_activates_and_redirects(client, customer):
    device = TOTPDevice.objects.create(user=customer, is_confirmed=False)
    client.force_login(customer)

    totp = pyotp.TOTP(device.secret_key)
    valid_code = totp.now()

    response = client.post(
        reverse("accounts:two_factor_verify"),
        {"code": valid_code},
        follow=True,
    )

    assert response.redirect_chain[-1][0] == reverse("accounts:two_factor_backup_codes")
    assert "Two-Factor Authentication is now enabled" in response.content.decode()

    device.refresh_from_db()
    assert device.is_confirmed
    assert customer.backup_codes.count() == 8


def test_two_factor_backup_codes_view_requires_confirmed_2fa(client, customer):
    client.force_login(customer)
    response = client.get(reverse("accounts:two_factor_backup_codes"))
    assert response.status_code == HTTPStatus.FOUND
    assert response.url == reverse("accounts:two_factor_setup")


def test_two_factor_backup_codes_regenerate_with_valid_password(client, customer):
    TOTPDevice.objects.create(user=customer, is_confirmed=True)
    BackupCode.generate_codes(customer, count=8)
    initial_hashes = set(customer.backup_codes.values_list("code_hash", flat=True))

    client.force_login(customer)
    response = client.post(
        reverse("accounts:two_factor_backup_codes"),
        {"password": "customer123"},
        follow=True,
    )

    assert response.redirect_chain[-1][0] == reverse("accounts:two_factor_backup_codes")
    assert "New backup recovery codes generated" in response.content.decode()

    new_hashes = set(customer.backup_codes.values_list("code_hash", flat=True))
    assert customer.backup_codes.count() == 8
    # Confirm all old codes were purged and replaced
    assert initial_hashes.isdisjoint(new_hashes)


def test_two_factor_backup_codes_regenerate_wrong_password_fails(client, customer):
    TOTPDevice.objects.create(user=customer, is_confirmed=True)
    BackupCode.generate_codes(customer, count=8)
    initial_hashes = set(customer.backup_codes.values_list("code_hash", flat=True))

    client.force_login(customer)
    response = client.post(
        reverse("accounts:two_factor_backup_codes"),
        {"password": "wrongpassword"},
    )

    assert response.status_code == HTTPStatus.OK
    assert response.context["form"].errors["password"]
    # Existing codes unaffected
    current_hashes = set(customer.backup_codes.values_list("code_hash", flat=True))
    assert initial_hashes == current_hashes


def test_two_factor_disable_requires_password(client, customer):
    TOTPDevice.objects.create(user=customer, is_confirmed=True)
    BackupCode.generate_codes(customer, count=8)

    client.force_login(customer)
    response = client.post(
        reverse("accounts:two_factor_disable"),
        {"password": "wrongpassword"},
    )

    assert response.status_code == HTTPStatus.OK
    assert response.context["form"].errors["password"]
    assert TOTPDevice.objects.filter(user=customer, is_confirmed=True).exists()
    assert customer.backup_codes.count() == 8


def test_two_factor_disable_success_removes_device_and_codes(client, customer):
    TOTPDevice.objects.create(user=customer, is_confirmed=True)
    BackupCode.generate_codes(customer, count=8)

    client.force_login(customer)
    response = client.post(
        reverse("accounts:two_factor_disable"),
        {"password": "customer123"},
        follow=True,
    )

    assert response.redirect_chain[-1][0] == reverse("accounts:security_center")
    assert "Two-factor authentication has been disabled." in response.content.decode()

    assert not TOTPDevice.objects.filter(user=customer).exists()
    assert not BackupCode.objects.filter(user=customer).exists()

    # Security center reflects disabled status
    content = response.content.decode()
    assert "Set Up 2FA" in content


# --- Two-Factor Sign-In Challenge & Rate Limiting (Phase 3) -----------------


def test_login_non_2fa_account_signs_in_directly(client, customer):
    cache.clear()
    response = client.post(
        reverse("accounts:login"),
        {"username": "customer", "password": "customer123"},
        follow=True,
    )

    assert response.redirect_chain[-1][0] == reverse("products:catalog")
    assert response.context["user"].is_authenticated
    assert response.context["user"] == customer


def test_login_2fa_enabled_account_redirects_to_challenge(client, customer):
    cache.clear()
    TOTPDevice.objects.create(user=customer, is_confirmed=True)

    response = client.post(
        reverse("accounts:login"),
        {"username": "customer", "password": "customer123"},
        follow=False,
    )

    assert response.status_code == HTTPStatus.FOUND
    assert response.url == reverse("accounts:two_factor_challenge")
    assert client.session.get("stage_2fa_user_id") == customer.pk

    # Verify user is not authenticated yet
    res = client.get(reverse("accounts:security_center"))
    assert res.status_code == HTTPStatus.FOUND
    assert reverse("accounts:login") in res.url


def test_two_factor_challenge_direct_access_without_staging_redirects_to_login(
    client, db
):
    response = client.get(reverse("accounts:two_factor_challenge"))
    assert response.status_code == HTTPStatus.FOUND
    assert response.url == reverse("accounts:login")

    response = client.post(reverse("accounts:two_factor_challenge"), {"code": "123456"})
    assert response.status_code == HTTPStatus.FOUND
    assert response.url == reverse("accounts:login")


def test_two_factor_challenge_with_valid_totp_completes_login(client, customer):
    cache.clear()
    device = TOTPDevice.objects.create(user=customer, is_confirmed=True)

    # Step 1: Initial login
    client.post(
        reverse("accounts:login"),
        {"username": "customer", "password": "customer123"},
    )

    # Step 2: 2FA challenge with valid TOTP code
    totp = pyotp.TOTP(device.secret_key)
    valid_code = totp.now()

    response = client.post(
        reverse("accounts:two_factor_challenge"),
        {"code": valid_code},
        follow=True,
    )

    assert response.redirect_chain[-1][0] == reverse("products:catalog")
    assert response.context["user"].is_authenticated
    assert response.context["user"] == customer
    assert "stage_2fa_user_id" not in client.session


def test_two_factor_challenge_with_backup_code_completes_login_and_consumes_code(
    client, customer
):
    cache.clear()
    TOTPDevice.objects.create(user=customer, is_confirmed=True)
    raw_codes = BackupCode.generate_codes(customer, count=8)
    chosen_code = raw_codes[0]

    # Step 1: Initial login
    client.post(
        reverse("accounts:login"),
        {"username": "customer", "password": "customer123"},
    )

    # Step 2: 2FA challenge with recovery code
    response = client.post(
        reverse("accounts:two_factor_challenge"),
        {"code": chosen_code},
        follow=True,
    )

    assert response.redirect_chain[-1][0] == reverse("products:catalog")
    assert response.context["user"].is_authenticated
    assert response.context["user"] == customer
    assert "Signed in using a backup recovery code" in response.content.decode()

    # Verify that code is now permanently marked used
    assert customer.backup_codes.filter(is_used=False).count() == 7
    assert customer.backup_codes.filter(is_used=True).count() == 1


def test_two_factor_challenge_reusing_consumed_backup_code_fails(client, customer):
    cache.clear()
    TOTPDevice.objects.create(user=customer, is_confirmed=True)
    raw_codes = BackupCode.generate_codes(customer, count=8)
    chosen_code = raw_codes[0]

    # Consume the code once
    assert BackupCode.verify_and_consume(customer, chosen_code)

    # Stage a new login attempt
    client.post(
        reverse("accounts:login"),
        {"username": "customer", "password": "customer123"},
    )

    # Try to reuse the consumed backup code
    response = client.post(
        reverse("accounts:two_factor_challenge"),
        {"code": chosen_code},
    )

    assert response.status_code == HTTPStatus.OK
    assert response.context["form"].errors["code"]


def test_two_factor_challenge_invalid_code_fails(client, customer):
    cache.clear()
    TOTPDevice.objects.create(user=customer, is_confirmed=True)

    client.post(
        reverse("accounts:login"),
        {"username": "customer", "password": "customer123"},
    )

    response = client.post(
        reverse("accounts:two_factor_challenge"),
        {"code": "999999"},
    )

    assert response.status_code == HTTPStatus.OK
    assert response.context["form"].errors["code"]


def test_two_factor_challenge_preserves_next_redirect(client, customer):
    cache.clear()
    device = TOTPDevice.objects.create(user=customer, is_confirmed=True)

    # Step 1: Login with ?next= query param
    client.post(
        reverse("accounts:login") + "?next=" + reverse("accounts:address_list"),
        {"username": "customer", "password": "customer123"},
    )

    # Step 2: 2FA challenge
    valid_code = pyotp.TOTP(device.secret_key).now()
    response = client.post(
        reverse("accounts:two_factor_challenge"),
        {"code": valid_code},
        follow=True,
    )

    assert response.redirect_chain[-1][0] == reverse("accounts:address_list")
    assert response.context["user"].is_authenticated


def test_login_rate_limiting(client, customer):
    cache.clear()

    # 5 failed login attempts
    for _ in range(5):
        res = client.post(
            reverse("accounts:login"),
            {"username": "customer", "password": "wrongpassword"},
        )
        assert res.status_code == HTTPStatus.OK

    # 6th attempt (even with right credentials) is locked out
    response = client.post(
        reverse("accounts:login"),
        {"username": "customer", "password": "customer123"},
    )
    assert response.status_code == HTTPStatus.OK
    content = response.content.decode()
    assert "Too many failed login attempts" in content


def test_two_factor_challenge_rate_limiting(client, customer):
    cache.clear()
    device = TOTPDevice.objects.create(user=customer, is_confirmed=True)

    # Stage login
    client.post(
        reverse("accounts:login"),
        {"username": "customer", "password": "customer123"},
    )

    # 5 failed 2FA challenge attempts
    for _ in range(5):
        res = client.post(
            reverse("accounts:two_factor_challenge"),
            {"code": "000000"},
        )
        assert res.status_code == HTTPStatus.OK

    # 6th attempt (even with valid TOTP code) is locked out
    valid_code = pyotp.TOTP(device.secret_key).now()
    response = client.post(
        reverse("accounts:two_factor_challenge"),
        {"code": valid_code},
    )
    assert response.status_code == HTTPStatus.OK
    content = response.content.decode()
    assert "Too many failed verification attempts" in content


# --- Session & Device Tracking with Revocation (Phase 4) --------------------


def test_parse_device_type_helper():
    assert (
        parse_device_type(
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15"
        )
        == "Mobile (iOS)"
    )
    assert (
        parse_device_type(
            "Mozilla/5.0 (iPad; CPU OS 16_5 like Mac OS X) AppleWebKit/605.1.15"
        )
        == "Tablet (iPadOS)"
    )
    assert (
        parse_device_type(
            "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 Mobile Safari/537.36"
        )
        == "Mobile (Android)"
    )
    assert (
        parse_device_type(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0"
        )
        == "Desktop (macOS)"
    )
    assert (
        parse_device_type(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        == "Desktop (Windows)"
    )
    assert parse_device_type("") == "Unknown Device"


def test_user_session_middleware_records_session_on_authenticated_request(
    client, customer
):
    client.force_login(customer)

    # Initial request creates UserSession
    client.get(
        reverse("products:catalog"),
        HTTP_USER_AGENT="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)",
        REMOTE_ADDR="198.51.100.42",
    )

    session_record = UserSession.objects.get(user=customer)
    assert session_record.device_type == "Mobile (iOS)"
    assert session_record.ip_address == "198.51.100.42"
    assert session_record.session_key == client.session.session_key

    # Subsequent request updates last_activity
    prev_activity = session_record.last_activity
    client.get(reverse("products:catalog"))
    session_record.refresh_from_db()
    assert session_record.last_activity >= prev_activity


def test_user_session_middleware_enforces_30_day_lifetime(client, customer):
    client.force_login(customer)
    session_key = client.session.session_key

    # Simulate session whose last activity was 35 days ago
    expired_time = timezone.now() - timedelta(days=35)
    UserSession.objects.create(
        user=customer,
        session_key=session_key,
        device_type="Desktop (macOS)",
        last_activity=expired_time,
    )

    # Make request to protected page
    response = client.get(reverse("accounts:security_center"))
    assert response.status_code == HTTPStatus.FOUND
    assert reverse("accounts:login") in response.url
    assert not UserSession.objects.filter(session_key=session_key).exists()


def test_session_list_view_requires_login(client, db):
    response = client.get(reverse("accounts:session_list"))
    assert response.status_code == HTTPStatus.FOUND
    assert reverse("accounts:login") in response.url


def test_session_list_view_renders_sessions_and_highlights_current(client, customer):
    other_user = get_user_model().objects.create_user(
        username="other_user", password="x"
    )

    client.force_login(customer)

    # Middleware creates the current session
    client.get(reverse("accounts:session_list"))

    # Create 2 other sessions for customer
    UserSession.objects.create(
        user=customer,
        session_key="sec_session_1",
        device_type="Tablet (iPadOS)",
        ip_address="192.0.2.1",
    )
    UserSession.objects.create(
        user=customer,
        session_key="sec_session_2",
        device_type="Desktop (Windows)",
        ip_address="192.0.2.2",
    )

    # Create a session for other_user
    UserSession.objects.create(
        user=other_user,
        session_key="other_user_session",
        device_type="Mobile (Android)",
        ip_address="192.0.2.3",
    )

    response = client.get(reverse("accounts:session_list"))
    assert response.status_code == HTTPStatus.OK
    content = response.content.decode()

    assert "Active Sessions & Devices" in content
    assert "Current Session" in content
    assert "Tablet (iPadOS)" in content
    assert "Desktop (Windows)" in content
    assert "Mobile (Android)" not in content
    assert "Sign out all other sessions" in content


def test_session_revoke_single_secondary_session(client, customer):
    client.force_login(customer)
    client.get(reverse("accounts:session_list"))

    # Create secondary session in database and session engine
    engine = import_module(settings.SESSION_ENGINE)
    sec_store = engine.SessionStore()
    sec_store.create()
    sec_key = sec_store.session_key

    sec_session = UserSession.objects.create(
        user=customer,
        session_key=sec_key,
        device_type="Mobile (Android)",
        ip_address="192.0.2.50",
    )

    response = client.post(
        reverse("accounts:session_revoke", kwargs={"pk": sec_session.pk}),
        follow=True,
    )

    assert response.redirect_chain[-1][0] == reverse("accounts:session_list")
    assert "Revoked session for Mobile (Android)." in response.content.decode()

    # Verify session record deleted
    assert not UserSession.objects.filter(pk=sec_session.pk).exists()

    # Verify Django session storage invalidated
    assert not engine.SessionStore().exists(sec_key)


def test_cannot_revoke_current_session_via_single_endpoint(client, customer):
    client.force_login(customer)
    client.get(reverse("accounts:session_list"))

    current_session = UserSession.objects.get(session_key=client.session.session_key)

    response = client.post(
        reverse("accounts:session_revoke", kwargs={"pk": current_session.pk}),
        follow=True,
    )

    assert response.redirect_chain[-1][0] == reverse("accounts:session_list")
    assert "cannot revoke your active current session" in response.content.decode()
    assert UserSession.objects.filter(pk=current_session.pk).exists()


def test_session_revoke_others_bulk_operation(client, customer):
    client.force_login(customer)
    client.get(reverse("accounts:session_list"))
    current_key = client.session.session_key

    engine = import_module(settings.SESSION_ENGINE)
    keys_to_revoke = []
    for i in range(3):
        store = engine.SessionStore()
        store.create()
        keys_to_revoke.append(store.session_key)
        UserSession.objects.create(
            user=customer,
            session_key=store.session_key,
            device_type=f"Device {i}",
        )

    assert UserSession.objects.filter(user=customer).count() == 4

    response = client.post(
        reverse("accounts:session_revoke_others"),
        follow=True,
    )

    assert response.redirect_chain[-1][0] == reverse("accounts:session_list")
    assert (
        "Successfully signed out 3 other active session(s)."
        in response.content.decode()
    )

    # Only current session remains
    remaining = UserSession.objects.filter(user=customer)
    assert remaining.count() == 1
    assert remaining.first().session_key == current_key

    # Invalidation confirmed in session engine
    for key in keys_to_revoke:
        assert not engine.SessionStore().exists(key)


def test_revoked_session_forced_to_sign_in(client, customer):
    from django.test import Client

    client_a = Client()
    client_b = Client()

    # Client A logs in
    client_a.post(
        reverse("accounts:login"),
        {"username": "customer", "password": "customer123"},
    )
    client_a.get(reverse("accounts:session_list"))

    # Client B logs in
    client_b.post(
        reverse("accounts:login"),
        {"username": "customer", "password": "customer123"},
    )
    client_b.get(reverse("accounts:session_list"))

    # Client A revokes all other sessions
    client_a.post(reverse("accounts:session_revoke_others"))

    # Client B makes a request to a protected endpoint
    response = client_b.get(reverse("accounts:security_center"))
    assert response.status_code == HTTPStatus.FOUND
    assert reverse("accounts:login") in response.url


# --- Security Audit Log & Critical Activity Alerts (Phase 5) ---------------


def test_login_success_logs_event_and_sends_new_device_email(client, customer):
    cache.clear()
    mail.outbox.clear()

    client.post(
        reverse("accounts:login"),
        {"username": "customer", "password": "customer123"},
        HTTP_USER_AGENT="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
    )

    # Event logged
    event = SecurityEvent.objects.filter(
        user=customer,
        event_type=SecurityEvent.EventType.LOGIN_SUCCESS,
    ).first()
    assert event is not None
    assert event.device_type == "Desktop (macOS)"

    # Transactional email alert sent for new device
    assert len(mail.outbox) == 1
    assert "New sign-in" in mail.outbox[0].subject
    assert customer.email in mail.outbox[0].to

    # Second login from same device does NOT resend new device email
    mail.outbox.clear()
    client.post(
        reverse("accounts:login"),
        {"username": "customer", "password": "customer123"},
        HTTP_USER_AGENT="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
    )
    assert len(mail.outbox) == 0


def test_login_failed_logs_event_for_existing_user(client, customer):
    cache.clear()
    client.post(
        reverse("accounts:login"),
        {"username": "customer", "password": "wrongpassword"},
        HTTP_USER_AGENT="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)",
    )

    event = SecurityEvent.objects.filter(
        user=customer,
        event_type=SecurityEvent.EventType.LOGIN_FAILED,
    ).first()
    assert event is not None
    assert event.device_type == "Mobile (iOS)"


def test_password_change_logs_event_and_sends_alert_email(client, customer):
    mail.outbox.clear()
    client.force_login(customer)

    client.post(
        reverse("accounts:password_change"),
        {
            "old_password": "customer123",
            "new_password1": "NewPassword789!",
            "new_password2": "NewPassword789!",
        },
    )

    event = SecurityEvent.objects.filter(
        user=customer,
        event_type=SecurityEvent.EventType.PASSWORD_CHANGED,
    ).first()
    assert event is not None

    assert len(mail.outbox) == 1
    assert "password" in mail.outbox[0].subject.lower()
    assert customer.email in mail.outbox[0].to


def test_two_factor_enable_logs_events_and_sends_alert_email(client, customer):
    mail.outbox.clear()
    device = TOTPDevice.objects.create(user=customer, is_confirmed=False)

    client.force_login(customer)
    valid_code = pyotp.TOTP(device.secret_key).now()

    client.post(
        reverse("accounts:two_factor_verify"),
        {"code": valid_code},
    )

    assert SecurityEvent.objects.filter(
        user=customer,
        event_type=SecurityEvent.EventType.TWO_FACTOR_ENABLED,
    ).exists()
    assert SecurityEvent.objects.filter(
        user=customer,
        event_type=SecurityEvent.EventType.BACKUP_CODES_GENERATED,
    ).exists()

    # Transactional alert email sent
    alert_mail = [
        m for m in mail.outbox if "Two-factor authentication enabled" in m.subject
    ]
    assert len(alert_mail) == 1
    assert customer.email in alert_mail[0].to


def test_two_factor_backup_codes_regenerate_logs_event(client, customer):
    TOTPDevice.objects.create(user=customer, is_confirmed=True)
    BackupCode.generate_codes(customer, count=8)

    client.force_login(customer)
    client.post(
        reverse("accounts:two_factor_backup_codes"),
        {"password": "customer123"},
    )

    event = (
        SecurityEvent.objects.filter(
            user=customer,
            event_type=SecurityEvent.EventType.BACKUP_CODES_GENERATED,
        )
        .order_by("-created_at")
        .first()
    )
    assert event is not None
    assert "Regenerated" in event.details


def test_two_factor_disable_logs_event_and_sends_alert_email(client, customer):
    mail.outbox.clear()
    TOTPDevice.objects.create(user=customer, is_confirmed=True)
    BackupCode.generate_codes(customer, count=8)

    client.force_login(customer)
    client.post(
        reverse("accounts:two_factor_disable"),
        {"password": "customer123"},
    )

    assert SecurityEvent.objects.filter(
        user=customer,
        event_type=SecurityEvent.EventType.TWO_FACTOR_DISABLED,
    ).exists()

    alert_mail = [m for m in mail.outbox if "disabled" in m.subject.lower()]
    assert len(alert_mail) == 1
    assert customer.email in alert_mail[0].to


def test_two_factor_challenge_backup_code_sign_in_logs_events(client, customer):
    cache.clear()
    TOTPDevice.objects.create(user=customer, is_confirmed=True)
    codes = BackupCode.generate_codes(customer, count=8)

    # Step 1
    client.post(
        reverse("accounts:login"),
        {"username": "customer", "password": "customer123"},
    )

    # Step 2
    client.post(
        reverse("accounts:two_factor_challenge"),
        {"code": codes[0]},
    )

    assert SecurityEvent.objects.filter(
        user=customer,
        event_type=SecurityEvent.EventType.BACKUP_CODE_USED,
    ).exists()
    assert SecurityEvent.objects.filter(
        user=customer,
        event_type=SecurityEvent.EventType.LOGIN_SUCCESS,
    ).exists()


def test_session_revoke_logs_event(client, customer):
    client.force_login(customer)
    client.get(reverse("accounts:session_list"))

    sec_session = UserSession.objects.create(
        user=customer,
        session_key="sec_key_abc",
        device_type="Tablet (iPadOS)",
        ip_address="198.51.100.99",
    )

    client.post(reverse("accounts:session_revoke", kwargs={"pk": sec_session.pk}))

    event = SecurityEvent.objects.filter(
        user=customer,
        event_type=SecurityEvent.EventType.SESSION_REVOKED,
    ).first()
    assert event is not None
    assert "Tablet (iPadOS)" in event.details


def test_session_revoke_others_logs_event(client, customer):
    client.force_login(customer)
    client.get(reverse("accounts:session_list"))

    UserSession.objects.create(
        user=customer,
        session_key="sec_key_xyz",
        device_type="Desktop (Windows)",
    )

    client.post(reverse("accounts:session_revoke_others"))

    event = SecurityEvent.objects.filter(
        user=customer,
        event_type=SecurityEvent.EventType.ALL_SESSIONS_REVOKED,
    ).first()
    assert event is not None


def test_security_activity_view_requires_login(client, db):
    response = client.get(reverse("accounts:security_activity"))
    assert response.status_code == HTTPStatus.FOUND
    assert reverse("accounts:login") in response.url


def test_security_activity_view_lists_events_chronologically(client, customer):
    client.force_login(customer)

    SecurityEvent.objects.create(
        user=customer,
        event_type=SecurityEvent.EventType.LOGIN_SUCCESS,
        device_type="Desktop (macOS)",
        ip_address="192.0.2.10",
    )
    SecurityEvent.objects.create(
        user=customer,
        event_type=SecurityEvent.EventType.TWO_FACTOR_ENABLED,
        device_type="Mobile (iOS)",
        ip_address="192.0.2.20",
    )

    response = client.get(reverse("accounts:security_activity"))
    assert response.status_code == HTTPStatus.OK
    content = response.content.decode()

    assert "Security Activity Log" in content
    assert "Sign in successful" in content
    assert "Two-factor authentication enabled" in content
    assert "Desktop (macOS)" in content
    assert "Mobile (iOS)" in content
