"""Unit tests for the checkout validators — pure functions, no database.

Coverage priority 1 in the PRD: these run before any form or view exists.
"""

import datetime

import pytest
from django.core.exceptions import ValidationError

from .validators import validate_card_number, validate_expiry

# --- validate_card_number ----------------------------------------------------


@pytest.mark.parametrize(
    "number",
    [
        "4242424242424242",
        "4111111111111111",
        "4242 4242 4242 4242",  # as people type it
        "4242-4242-4242-4242",
    ],
)
def test_accepts_known_test_numbers(number):
    validate_card_number(number)  # must not raise


@pytest.mark.parametrize(
    "number",
    [
        "4242424242424241",  # corrupted final digit
        "4111111111111112",
        "1234567890123456",
    ],
)
def test_rejects_corrupted_numbers(number):
    with pytest.raises(ValidationError):
        validate_card_number(number)


@pytest.mark.parametrize(
    "number",
    [
        "",
        "4242",  # too short
        "42424242424242424242",  # too long
        "4242 4242 4242 424x",  # non-digit
        "card number",
    ],
)
def test_rejects_malformed_numbers(number):
    with pytest.raises(ValidationError):
        validate_card_number(number)


# --- validate_expiry ---------------------------------------------------------


def _mm_yy(date):
    return date.strftime("%m/%y")


def test_accepts_the_current_month():
    validate_expiry(_mm_yy(datetime.date.today()))


def test_accepts_a_future_date():
    future = datetime.date.today() + datetime.timedelta(days=730)
    validate_expiry(_mm_yy(future))


def test_rejects_last_month():
    last_month = datetime.date.today().replace(day=1) - datetime.timedelta(days=1)
    with pytest.raises(ValidationError):
        validate_expiry(_mm_yy(last_month))


def test_rejects_a_long_expired_card():
    with pytest.raises(ValidationError):
        validate_expiry("01/20")


@pytest.mark.parametrize(
    "value",
    ["", "13/30", "00/30", "1230", "12-30", "12/2030", "MM/YY"],
)
def test_rejects_malformed_expiry(value):
    with pytest.raises(ValidationError):
        validate_expiry(value)
