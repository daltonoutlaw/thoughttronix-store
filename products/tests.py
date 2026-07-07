from http import HTTPStatus

from django.urls import reverse


def test_catalog_displays_product(client, product):
    """The catalog page returns 200 and shows a product's name, category, and price."""
    response = client.get(reverse("products:catalog"))

    assert response.status_code == HTTPStatus.OK
    page = response.content.decode()
    assert product.name in page
    assert product.category.name in page
    assert str(product.price) in page
