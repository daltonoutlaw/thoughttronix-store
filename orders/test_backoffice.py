"""Back-office order management: access control, the status filter, updates."""

from decimal import Decimal
from http import HTTPStatus

import pytest
from django.urls import reverse

from .models import Order
from .services import place_order
from .test_checkout_form import VALID_DATA

pytestmark = pytest.mark.django_db


@pytest.fixture
def order(cart, cart_item):
    return place_order(cart, cart.user, dict(VALID_DATA))


@pytest.fixture
def shipped_order(customer):
    return Order.objects.create(
        user=customer,
        status=Order.Status.SHIPPED,
        total=Decimal("9.00"),
        email="casey@example.com",
        shipping_name="Casey Monroe",
        shipping_street="9 Synapse Court",
        shipping_city="Canyon",
        shipping_state="TX",
        shipping_zip="79015",
        billing_name="Casey Monroe",
        billing_street="9 Synapse Court",
        billing_city="Canyon",
        billing_state="TX",
        billing_zip="79015",
        card_last4="4242",
    )


def manage_urls(order):
    return [
        reverse("orders:manage_orders"),
        reverse("orders:manage_order_detail", kwargs={"pk": order.pk}),
        reverse("orders:manage_order_status", kwargs={"pk": order.pk}),
    ]


# --- Access control ----------------------------------------------------------


def test_anonymous_users_are_sent_to_login(client, order):
    for url in manage_urls(order):
        response = client.get(url)

        assert response.status_code == HTTPStatus.FOUND, url
        assert reverse("accounts:login") in response.url


def test_customers_get_403(client, customer, order):
    client.force_login(customer)

    for url in manage_urls(order):
        assert client.get(url).status_code == HTTPStatus.FORBIDDEN, url


# --- The order list ----------------------------------------------------------


def test_staff_see_every_customers_orders(client, staff_user, order, shipped_order):
    client.force_login(staff_user)

    page = client.get(reverse("orders:manage_orders")).content.decode()

    assert order.number in page
    assert shipped_order.number in page
    assert order.user.username in page


def test_list_filters_by_status(client, staff_user, order, shipped_order):
    client.force_login(staff_user)

    page = client.get(
        reverse("orders:manage_orders"), {"status": "SHIPPED"}
    ).content.decode()

    assert shipped_order.number in page
    assert order.number not in page


def test_unknown_status_filter_is_ignored(client, staff_user, order, shipped_order):
    client.force_login(staff_user)

    page = client.get(
        reverse("orders:manage_orders"), {"status": "TELEPORTED"}
    ).content.decode()

    assert order.number in page
    assert shipped_order.number in page


def test_list_has_a_designed_empty_state(client, staff_user):
    client.force_login(staff_user)

    assert (
        "No orders yet" in client.get(reverse("orders:manage_orders")).content.decode()
    )


def test_filtered_empty_state_offers_to_clear(client, staff_user, order):
    client.force_login(staff_user)

    page = client.get(
        reverse("orders:manage_orders"), {"status": "DELIVERED"}
    ).content.decode()

    assert "No orders with that status" in page


# --- Order detail and status updates -----------------------------------------


def test_detail_shows_the_customer_and_both_addresses(client, staff_user, order):
    client.force_login(staff_user)

    page = client.get(
        reverse("orders:manage_order_detail", kwargs={"pk": order.pk})
    ).content.decode()

    assert order.number in page
    assert order.user.username in page
    assert "Shipping address" in page
    assert "Billing address" in page
    assert "card ending 4242" in page


def test_staff_can_update_an_orders_status(client, staff_user, order):
    client.force_login(staff_user)

    response = client.post(
        reverse("orders:manage_order_status", kwargs={"pk": order.pk}),
        {"status": "SHIPPED"},
        follow=True,
    )

    order.refresh_from_db()
    assert order.status == Order.Status.SHIPPED
    assert "is now shipped" in response.content.decode()


def test_an_unknown_status_is_rejected(client, staff_user, order):
    client.force_login(staff_user)

    client.post(
        reverse("orders:manage_order_status", kwargs={"pk": order.pk}),
        {"status": "TELEPORTED"},
    )

    order.refresh_from_db()
    assert order.status == Order.Status.PLACED
