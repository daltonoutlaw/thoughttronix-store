"""The checkout form — the codebase's showcase of declarative validation.

Every rule is visible at its field declaration, in the style of data
annotations: field types validate (``EmailField``), field arguments
validate (``required``, ``max_length``, ``ChoiceField``), and the
``validators=[...]`` list carries the rest. No ``clean_*`` methods
and no ``clean()`` — none of its current rules need imperative validation.
"""

from django import forms
from django.core.validators import RegexValidator

from .models import Order
from .validators import validate_card_number, validate_expiry

US_STATES = [
    ("AL", "Alabama"),
    ("AK", "Alaska"),
    ("AZ", "Arizona"),
    ("AR", "Arkansas"),
    ("CA", "California"),
    ("CO", "Colorado"),
    ("CT", "Connecticut"),
    ("DE", "Delaware"),
    ("DC", "District of Columbia"),
    ("FL", "Florida"),
    ("GA", "Georgia"),
    ("HI", "Hawaii"),
    ("ID", "Idaho"),
    ("IL", "Illinois"),
    ("IN", "Indiana"),
    ("IA", "Iowa"),
    ("KS", "Kansas"),
    ("KY", "Kentucky"),
    ("LA", "Louisiana"),
    ("ME", "Maine"),
    ("MD", "Maryland"),
    ("MA", "Massachusetts"),
    ("MI", "Michigan"),
    ("MN", "Minnesota"),
    ("MS", "Mississippi"),
    ("MO", "Missouri"),
    ("MT", "Montana"),
    ("NE", "Nebraska"),
    ("NV", "Nevada"),
    ("NH", "New Hampshire"),
    ("NJ", "New Jersey"),
    ("NM", "New Mexico"),
    ("NY", "New York"),
    ("NC", "North Carolina"),
    ("ND", "North Dakota"),
    ("OH", "Ohio"),
    ("OK", "Oklahoma"),
    ("OR", "Oregon"),
    ("PA", "Pennsylvania"),
    ("RI", "Rhode Island"),
    ("SC", "South Carolina"),
    ("SD", "South Dakota"),
    ("TN", "Tennessee"),
    ("TX", "Texas"),
    ("UT", "Utah"),
    ("VT", "Vermont"),
    ("VA", "Virginia"),
    ("WA", "Washington"),
    ("WV", "West Virginia"),
    ("WI", "Wisconsin"),
    ("WY", "Wyoming"),
]

zip_validator = RegexValidator(
    r"^\d{5}(-\d{4})?$", "Enter a ZIP code like 79016 or 79016-1234."
)
cvv_validator = RegexValidator(r"^\d{3,4}$", "Enter the 3- or 4-digit CVV.")


class CheckoutForm(forms.Form):
    """One page, one POST: contact, shipping, billing, payment."""

    email = forms.EmailField(label="Email")

    shipping_address_choice = forms.ChoiceField(
        label="Saved shipping address", required=False
    )
    shipping_name = forms.CharField(label="Full name", max_length=100)
    shipping_street = forms.CharField(label="Street address", max_length=200)
    shipping_line2 = forms.CharField(
        label="Apt, suite, etc. (optional)", max_length=200, required=False
    )
    shipping_city = forms.CharField(label="City", max_length=100)
    shipping_state = forms.ChoiceField(label="State", choices=US_STATES)
    shipping_zip = forms.CharField(
        label="ZIP code", max_length=10, validators=[zip_validator]
    )
    save_shipping_address = forms.BooleanField(
        label="Save this address to my account", required=False
    )
    set_default_shipping = forms.BooleanField(
        label="Set as default shipping address", required=False
    )

    billing_address_choice = forms.ChoiceField(
        label="Saved billing address", required=False
    )
    billing_name = forms.CharField(label="Full name", max_length=100)
    billing_street = forms.CharField(label="Street address", max_length=200)
    billing_line2 = forms.CharField(
        label="Apt, suite, etc. (optional)", max_length=200, required=False
    )
    billing_city = forms.CharField(label="City", max_length=100)
    billing_state = forms.ChoiceField(label="State", choices=US_STATES)
    billing_zip = forms.CharField(
        label="ZIP code", max_length=10, validators=[zip_validator]
    )
    save_billing_address = forms.BooleanField(
        label="Save this address to my account", required=False
    )
    set_default_billing = forms.BooleanField(
        label="Set as default billing address", required=False
    )

    card_number = forms.CharField(
        label="Card number", max_length=23, validators=[validate_card_number]
    )
    card_expiry = forms.CharField(
        label="Expiry (MM/YY)", max_length=5, validators=[validate_expiry]
    )
    card_cvv = forms.CharField(label="CVV", max_length=4, validators=[cvv_validator])

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

        if user and user.is_authenticated and hasattr(user, "addresses"):
            addresses = list(user.addresses.all())
            if addresses:
                choices = [(str(addr.pk), str(addr)) for addr in addresses]
                choices.append(("new", "Enter new address"))
                self.fields["shipping_address_choice"].choices = choices
                self.fields["billing_address_choice"].choices = choices

                if not self.is_bound:
                    default_shipping = next(
                        (a for a in addresses if a.is_default_shipping), addresses[0]
                    )
                    default_billing = next(
                        (a for a in addresses if a.is_default_billing), addresses[0]
                    )

                    self.initial.setdefault(
                        "shipping_address_choice", str(default_shipping.pk)
                    )
                    self.initial.setdefault("shipping_name", default_shipping.name)
                    self.initial.setdefault("shipping_street", default_shipping.street)
                    self.initial.setdefault("shipping_line2", default_shipping.line2)
                    self.initial.setdefault("shipping_city", default_shipping.city)
                    self.initial.setdefault("shipping_state", default_shipping.state)
                    self.initial.setdefault("shipping_zip", default_shipping.zip)

                    self.initial.setdefault(
                        "billing_address_choice", str(default_billing.pk)
                    )
                    self.initial.setdefault("billing_name", default_billing.name)
                    self.initial.setdefault("billing_street", default_billing.street)
                    self.initial.setdefault("billing_line2", default_billing.line2)
                    self.initial.setdefault("billing_city", default_billing.city)
                    self.initial.setdefault("billing_state", default_billing.state)
                    self.initial.setdefault("billing_zip", default_billing.zip)
            else:
                self.fields["shipping_address_choice"].choices = [
                    ("new", "Enter new address")
                ]
                self.fields["billing_address_choice"].choices = [
                    ("new", "Enter new address")
                ]
                if not self.is_bound:
                    self.initial.setdefault("shipping_address_choice", "new")
                    self.initial.setdefault("billing_address_choice", "new")
        else:
            self.fields["shipping_address_choice"].choices = [
                ("new", "Enter new address")
            ]
            self.fields["billing_address_choice"].choices = [
                ("new", "Enter new address")
            ]

        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs["class"] = "checkbox checkbox-primary"
            elif isinstance(widget, forms.Select):
                widget.attrs["class"] = "select w-full"
            else:
                widget.attrs["class"] = "input w-full"

    # Field groups for the template — the form owns its own structure.

    def shipping_address_fields(self):
        return [
            self["shipping_name"],
            self["shipping_street"],
            self["shipping_line2"],
            self["shipping_city"],
            self["shipping_state"],
            self["shipping_zip"],
        ]

    def billing_address_fields(self):
        return [
            self["billing_name"],
            self["billing_street"],
            self["billing_line2"],
            self["billing_city"],
            self["billing_state"],
            self["billing_zip"],
        ]

    def shipping_fields(self):
        return [self[name] for name in self.fields if name.startswith("shipping_")]

    def billing_fields(self):
        return [self[name] for name in self.fields if name.startswith("billing_")]

    def card_fields(self):
        return [self[name] for name in self.fields if name.startswith("card_")]


class OrderStatusForm(forms.ModelForm):
    """The back-office status dropdown — any of the four states, anytime.

    Guarding the workflow (no un-cancelling, no re-shipping a delivered
    order) is deliberately left as a student exercise.
    """

    class Meta:
        model = Order
        fields = ["status"]
        widgets = {"status": forms.Select(attrs={"class": "select"})}
