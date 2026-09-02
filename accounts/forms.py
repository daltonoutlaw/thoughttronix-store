from django import forms
from django.contrib.auth.forms import (
    AuthenticationForm,
    UserCreationForm,
)
from django.contrib.auth.forms import (
    PasswordChangeForm as DjangoPasswordChangeForm,
)

from orders.forms import US_STATES, zip_validator

from .models import Address, BackupCode, User


class SignupForm(UserCreationForm):
    """Django's stock signup fields — username plus password and confirmation.

    No email: signing up asks for the minimum. The widgets carry DaisyUI
    classes because plain Django forms own their own styling here.
    """

    class Meta(UserCreationForm.Meta):
        model = User

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "input w-full"


class SignInForm(AuthenticationForm):
    """The stock authentication form, dressed in DaisyUI."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "input w-full"


class AddressForm(forms.ModelForm):
    """Form for adding and editing customer saved addresses."""

    state = forms.ChoiceField(label="State", choices=US_STATES)
    zip = forms.CharField(label="ZIP code", max_length=10, validators=[zip_validator])

    class Meta:
        model = Address
        fields = [
            "label",
            "name",
            "street",
            "line2",
            "city",
            "state",
            "zip",
            "is_default_shipping",
            "is_default_billing",
        ]
        labels = {
            "label": "Address label (optional, e.g. Home, Work)",
            "name": "Full name",
            "street": "Street address",
            "line2": "Apt, suite, etc. (optional)",
            "city": "City",
            "is_default_shipping": "Default shipping address",
            "is_default_billing": "Default billing address",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs["class"] = "checkbox checkbox-primary"
            elif isinstance(widget, forms.Select):
                widget.attrs["class"] = "select w-full"
            else:
                widget.attrs["class"] = "input w-full"


class PasswordChangeForm(DjangoPasswordChangeForm):
    """Step-up password change form dressed in DaisyUI."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "input w-full"


class PasswordConfirmForm(forms.Form):
    """Step-up confirmation form validating the user's current password."""

    password = forms.CharField(
        label="Current password",
        widget=forms.PasswordInput(
            attrs={
                "class": "input w-full",
                "placeholder": "Enter your current password",
            }
        ),
    )

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_password(self):
        password = self.cleaned_data.get("password")
        if not self.user.check_password(password):
            raise forms.ValidationError("Incorrect password. Please try again.")
        return password


class TOTPVerifyForm(forms.Form):
    """Form to submit and verify a 6-digit TOTP token."""

    code = forms.CharField(
        label="6-digit verification code",
        max_length=6,
        min_length=6,
        widget=forms.TextInput(
            attrs={
                "class": "input w-full font-mono text-center tracking-widest text-lg",
                "placeholder": "123456",
                "autocomplete": "one-time-code",
                "inputmode": "numeric",
                "pattern": "[0-9]{6}",
                "autofocus": True,
            }
        ),
    )

    def clean_code(self):
        code = self.cleaned_data.get("code", "").strip()
        if not code.isdigit() or len(code) != 6:
            raise forms.ValidationError("Please enter a valid 6-digit numeric code.")
        return code


class TwoFactorChallengeForm(forms.Form):
    """Form for secondary authentication using a TOTP code or backup code."""

    code = forms.CharField(
        label="Verification code",
        max_length=32,
        widget=forms.TextInput(
            attrs={
                "class": "input w-full font-mono text-center tracking-widest text-lg",
                "placeholder": "6-digit code or recovery code",
                "autocomplete": "one-time-code",
                "autofocus": True,
            }
        ),
    )

    def __init__(self, user, *args, **kwargs):
        self.user = user
        self.used_backup_code = False
        super().__init__(*args, **kwargs)

    def clean_code(self):
        raw_code = self.cleaned_data.get("code", "").strip()
        if not raw_code:
            raise forms.ValidationError("Please enter a verification code.")

        # 1. Try TOTP code if it's 6 digits
        if raw_code.isdigit() and len(raw_code) == 6:
            totp_device = getattr(self.user, "totp_device", None)
            if totp_device and totp_device.is_confirmed:
                if totp_device.verify_code(raw_code):
                    return raw_code

        # 2. Try single-use backup recovery code
        if BackupCode.verify_and_consume(self.user, raw_code):
            self.used_backup_code = True
            return raw_code

        raise forms.ValidationError(
            "Invalid verification code. Please check your authenticator app or enter a valid backup recovery code."
        )
