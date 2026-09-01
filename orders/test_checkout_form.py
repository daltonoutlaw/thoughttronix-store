"""CheckoutForm tests — coverage priority 2 in the PRD.

Each declarative rule rejects bad input with a field-specific error;
a fully valid form passes. No database required.
"""

import pytest

from .forms import CheckoutForm

VALID_DATA = {
    "email": "casey@example.com",
    "shipping_name": "Casey Monroe",
    "shipping_street": "12 Cortex Lane",
    "shipping_line2": "Unit 7",
    "shipping_city": "Canyon",
    "shipping_state": "TX",
    "shipping_zip": "79015",
    "billing_name": "Casey Monroe",
    "billing_street": "12 Cortex Lane",
    "billing_line2": "",
    "billing_city": "Canyon",
    "billing_state": "TX",
    "billing_zip": "79015-1234",
    "card_number": "4242 4242 4242 4242",
    "card_expiry": "12/39",
    "card_cvv": "123",
}


def form_with(**overrides):
    return CheckoutForm(data={**VALID_DATA, **overrides})


def test_a_fully_valid_form_passes():
    assert form_with().is_valid()


def test_line2_is_optional_but_everything_else_is_required():
    required = [name for name in VALID_DATA if not name.endswith("_line2")]
    for name in required:
        form = form_with(**{name: ""})
        assert not form.is_valid()
        assert form.errors[name] == ["This field is required."]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("email", "not-an-email"),
        ("shipping_state", "XX"),  # not one of the 50 states + DC
        ("billing_state", "Texas"),
        ("shipping_zip", "790"),
        ("billing_zip", "79015-12"),
        ("card_number", "4242 4242 4242 4241"),  # fails Luhn
        ("card_expiry", "01/20"),  # long expired
        ("card_expiry", "13/30"),  # no thirteenth month
        ("card_cvv", "12"),
        ("card_cvv", "abcd"),
    ],
)
def test_each_rule_rejects_bad_input_on_its_own_field(field, value):
    form = form_with(**{field: value})

    assert not form.is_valid()
    assert field in form.errors
    assert len(form.errors) == 1  # the error lands beside its field, alone


def test_the_form_declares_no_imperative_validation():
    """The showcase contract: declarative rules only, per the PRD."""
    assert "clean" not in CheckoutForm.__dict__
    assert not any(name.startswith("clean_") for name in CheckoutForm.__dict__)


def test_form_with_user_prepopulates_default_addresses(customer):
    from accounts.models import Address

    addr = Address.objects.create(
        user=customer,
        name="Casey Default",
        street="100 Prime Way",
        city="Austin",
        state="TX",
        zip="78701",
    )
    form = CheckoutForm(user=customer)

    assert form.initial["shipping_address_choice"] == str(addr.pk)
    assert form.initial["shipping_name"] == "Casey Default"
    assert form.initial["shipping_street"] == "100 Prime Way"
    assert form.initial["billing_name"] == "Casey Default"
    assert len(form.fields["shipping_address_choice"].choices) == 2  # addr + new
