"""Project-wide pytest fixtures.

Shared test data lives here as plain fixtures — no factories. The suite
grows with the project; tests never invoke the seed command.
"""

from decimal import Decimal

import pytest

from products.models import Category, Product


@pytest.fixture
def category(db):
    return Category.objects.create(name="Seraphine")


@pytest.fixture
def product(category):
    return Product.objects.create(
        name="Seraphine Home Hub",
        slug="seraphine-home-hub",
        price=Decimal("349.99"),
        category=category,
    )
