from http import HTTPStatus

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.urls import reverse

from products.models import Product

from .models import Wishlist, WishlistItem

# --- Model behavior ---------------------------------------------------------


def test_wishlist_str(wishlist):
    assert str(wishlist) == "Wishlist for customer"


def test_wishlist_item_str(wishlist_item):
    assert str(wishlist_item) == "Seraphine Home Hub in Wishlist for customer"


def test_for_user_creates_wishlist_once(customer):
    first = Wishlist.for_user(customer)
    second = Wishlist.for_user(customer)

    assert first == second
    assert Wishlist.objects.count() == 1


def test_add_creates_wishlist_item(wishlist, product):
    item = wishlist.add(product)

    assert item.product == product
    assert item.wishlist == wishlist
    assert wishlist.items.count() == 1


def test_duplicate_add_does_not_duplicate(wishlist, product):
    wishlist.add(product)
    wishlist.add(product)

    assert wishlist.items.count() == 1


def test_wishlist_product_pair_is_unique(wishlist_item):
    with pytest.raises(IntegrityError):
        WishlistItem.objects.create(
            wishlist=wishlist_item.wishlist,
            product=wishlist_item.product,
        )


def test_contains_method(wishlist, product):
    assert not wishlist.contains(product)

    wishlist.add(product)
    assert wishlist.contains(product)

    wishlist.remove(product)
    assert not wishlist.contains(product)


def test_remove_nonexistent_product_is_noop(wishlist, product):
    wishlist.remove(product)
    assert wishlist.items.count() == 0


def test_toggle_method_adds_and_removes(wishlist, product):
    # First toggle: adds product -> returns True
    added = wishlist.toggle(product)
    assert added is True
    assert wishlist.contains(product)
    assert wishlist.items.count() == 1

    # Second toggle: removes product -> returns False
    removed = wishlist.toggle(product)
    assert removed is False
    assert not wishlist.contains(product)
    assert wishlist.items.count() == 0


def test_wishlist_can_hold_unavailable_products(wishlist, unavailable_product):
    added = wishlist.toggle(unavailable_product)

    assert added is True
    assert wishlist.contains(unavailable_product)


# --- Wishlist Toggle View (HTMX) --------------------------------------------


def test_anonymous_toggle_redirects_to_login(client, product):
    response = client.post(reverse("wishlists:toggle", kwargs={"pk": product.pk}))

    assert response.status_code == HTTPStatus.FOUND
    assert reverse("accounts:login") in response.url


def test_anonymous_product_detail_shows_login_link(client, product):
    response = client.get(product.get_absolute_url())

    assert response.status_code == HTTPStatus.OK
    page = response.content.decode()
    assert f"{reverse('accounts:login')}?next=" in page
    assert "Add to Wishlist" in page


def test_toggle_endpoint_adds_product_and_returns_partial(client, customer, product):
    client.force_login(customer)

    response = client.post(reverse("wishlists:toggle", kwargs={"pk": product.pk}))

    assert response.status_code == HTTPStatus.OK
    page = response.content.decode()
    assert "<html" not in page
    assert "In Wishlist (Remove)" in page
    assert customer.wishlist.contains(product)


def test_toggle_endpoint_removes_product_and_returns_partial(
    client, customer, wishlist_item
):
    client.force_login(customer)

    response = client.post(
        reverse("wishlists:toggle", kwargs={"pk": wishlist_item.product.pk})
    )

    assert response.status_code == HTTPStatus.OK
    page = response.content.decode()
    assert "<html" not in page
    assert "Add to Wishlist" in page
    assert not customer.wishlist.contains(wishlist_item.product)


def test_toggle_unavailable_product_succeeds(client, customer, unavailable_product):
    client.force_login(customer)

    response = client.post(
        reverse("wishlists:toggle", kwargs={"pk": unavailable_product.pk})
    )

    assert response.status_code == HTTPStatus.OK
    page = response.content.decode()
    assert "<html" not in page
    assert "In Wishlist (Remove)" in page
    assert customer.wishlist.contains(unavailable_product)


def test_toggle_nonexistent_product_404s(client, customer):
    client.force_login(customer)

    response = client.post(reverse("wishlists:toggle", kwargs={"pk": 999999}))

    assert response.status_code == HTTPStatus.NOT_FOUND


def test_product_detail_shows_add_to_wishlist_state(client, customer, product):
    client.force_login(customer)

    response = client.get(product.get_absolute_url())

    assert response.status_code == HTTPStatus.OK
    page = response.content.decode()
    assert "Add to Wishlist" in page
    assert "In Wishlist (Remove)" not in page


def test_product_detail_shows_in_wishlist_state(client, customer, wishlist_item):
    client.force_login(customer)

    response = client.get(wishlist_item.product.get_absolute_url())

    assert response.status_code == HTTPStatus.OK
    page = response.content.decode()
    assert "In Wishlist (Remove)" in page


def test_customer_data_isolation(client, customer, wishlist_item):
    other = get_user_model().objects.create_user(
        username="other_customer",
        password="password123",
        email="other@thoughttronix.example",
    )
    client.force_login(other)

    # Other customer's detail view should show "Add to Wishlist"
    response = client.get(wishlist_item.product.get_absolute_url())
    assert "Add to Wishlist" in response.content.decode()
    assert "In Wishlist (Remove)" not in response.content.decode()

    # Other customer toggling does not affect original customer's wishlist
    client.post(reverse("wishlists:toggle", kwargs={"pk": wishlist_item.product.pk}))
    assert other.wishlist.contains(wishlist_item.product)
    assert customer.wishlist.contains(wishlist_item.product)


# --- Wishlist Detail View ---------------------------------------------------


def test_wishlist_detail_requires_authentication(client):
    response = client.get(reverse("wishlists:detail"))

    assert response.status_code == HTTPStatus.FOUND
    assert reverse("accounts:login") in response.url


def test_wishlist_detail_renders_items_and_isolates_customers(
    client, customer, wishlist_item, unavailable_product
):
    # Add a second item so we can verify ordering (most recent first)
    second_item = customer.wishlist.add(unavailable_product)

    # Another customer with their own item
    other_customer = get_user_model().objects.create_user(
        username="other_customer",
        password="password123",
        email="other@thoughttronix.example",
    )
    other_product = Product.objects.create(
        name="Secret Neural Visor",
        slug="secret-neural-visor",
        price=199.99,
        category=wishlist_item.product.category,
    )
    Wishlist.for_user(other_customer).add(other_product)

    client.force_login(customer)
    response = client.get(reverse("wishlists:detail"))

    assert response.status_code == HTTPStatus.OK
    page = response.content.decode()

    # Customer sees their own items
    assert wishlist_item.product.name in page
    assert unavailable_product.name in page
    assert wishlist_item.product.get_absolute_url() in page
    assert unavailable_product.get_absolute_url() in page
    assert f"${wishlist_item.product.price:,.2f}" in page
    assert "In stock" in page
    assert "Unavailable" in page

    # Context items are ordered by most recently added (-added_at)
    items = list(response.context["items"])
    assert items == [second_item, wishlist_item]

    # Customer does NOT see other customer's items
    assert "Secret Neural Visor" not in page


def test_navbar_renders_wishlist_link_for_authenticated_customer(client, customer):
    # Anonymous visitor does not see the wishlist navigation link
    response = client.get(reverse("products:catalog"))
    assert response.status_code == HTTPStatus.OK
    assert reverse("wishlists:detail") not in response.content.decode()

    # Authenticated customer sees the wishlist navigation link
    client.force_login(customer)
    response = client.get(reverse("products:catalog"))
    assert response.status_code == HTTPStatus.OK
    page = response.content.decode()
    assert reverse("wishlists:detail") in page
    assert "Wishlist" in page


def test_wishlist_detail_renders_empty_state_when_no_items(client, customer):
    client.force_login(customer)
    response = client.get(reverse("wishlists:detail"))

    assert response.status_code == HTTPStatus.OK
    page = response.content.decode()
    assert "Your wishlist is empty" in page
    assert "Save items you want to keep track of or buy later." in page
    assert reverse("products:catalog") in page
    assert "Browse the catalog" in page
    assert "0 items saved" in page
    assert response.context["items"].count() == 0


def test_remove_endpoint_removes_product_and_isolates_customers(
    client, customer, wishlist_item, unavailable_product
):
    # Customer has two items
    customer.wishlist.add(unavailable_product)

    # Another customer has their own item
    other_customer = get_user_model().objects.create_user(
        username="other_customer",
        password="password123",
        email="other@thoughttronix.example",
    )
    Wishlist.for_user(other_customer).add(wishlist_item.product)

    client.force_login(customer)
    response = client.post(
        reverse("wishlists:remove", kwargs={"pk": wishlist_item.product.pk})
    )

    assert response.status_code == HTTPStatus.OK
    page = response.content.decode()
    # Customer no longer has the removed item
    assert not customer.wishlist.contains(wishlist_item.product)
    # Customer still has the remaining item
    assert customer.wishlist.contains(unavailable_product)
    # Other customer's item is NOT removed
    assert other_customer.wishlist.contains(wishlist_item.product)
    # The returned partial shows the remaining item and not the removed item
    assert unavailable_product.name in page
    assert wishlist_item.product.name not in page
    # Not a full page reload
    assert "<html" not in page


def test_removing_final_item_renders_empty_state_partial(
    client, customer, wishlist_item
):
    client.force_login(customer)
    response = client.post(
        reverse("wishlists:remove", kwargs={"pk": wishlist_item.product.pk})
    )

    assert response.status_code == HTTPStatus.OK
    page = response.content.decode()
    assert "<html" not in page
    assert "Your wishlist is empty" in page
    assert "0 items saved" in page
    assert reverse("products:catalog") in page
    assert wishlist_item.product.name not in page


def test_wishlist_page_renders_cart_actions_for_available_and_unavailable_products(
    client, customer, wishlist_item, unavailable_product
):
    customer.wishlist.add(unavailable_product)

    client.force_login(customer)
    response = client.get(reverse("wishlists:detail"))

    assert response.status_code == HTTPStatus.OK
    page = response.content.decode()

    # For available product: in-stock badge and active Add to Cart HTMX button
    assert wishlist_item.product.name in page
    assert reverse("orders:add", kwargs={"pk": wishlist_item.product.pk}) in page
    assert "Add to cart" in page

    # For unavailable product: out-of-stock badge and disabled Unavailable button
    assert unavailable_product.name in page
    assert "Unavailable" in page
    assert (
        f'hx-post="{reverse("orders:add", kwargs={"pk": unavailable_product.pk})}"'
        not in page
    )


def test_cart_addition_from_wishlist_integration(client, customer, wishlist_item):
    client.force_login(customer)

    # Post to orders:add using product pk from wishlist item
    response = client.post(
        reverse("orders:add", kwargs={"pk": wishlist_item.product.pk})
    )

    assert response.status_code == HTTPStatus.OK
    from orders.models import Cart

    cart = Cart.for_user(customer)
    assert cart.items.filter(product=wishlist_item.product).exists()
    assert cart.items.get(product=wishlist_item.product).quantity == 1


def test_cannot_add_unavailable_product_to_cart(client, customer, unavailable_product):
    client.force_login(customer)

    response = client.post(reverse("orders:add", kwargs={"pk": unavailable_product.pk}))

    assert response.status_code == HTTPStatus.NOT_FOUND
