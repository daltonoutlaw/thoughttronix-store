from http import HTTPStatus

from django.contrib.auth import get_user_model
from django.core import mail
from django.urls import reverse

from .models import Address

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
