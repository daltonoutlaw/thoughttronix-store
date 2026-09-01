from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import (
    LoginView,
    LogoutView,
)
from django.contrib.auth.views import (
    PasswordChangeView as AuthPasswordChangeView,
)
from django.contrib.messages.views import SuccessMessageMixin
from django.core.mail import send_mail
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import (
    CreateView,
    DeleteView,
    ListView,
    TemplateView,
    UpdateView,
)

from .forms import AddressForm, PasswordChangeForm, SignInForm, SignupForm
from .models import Address


class SignupView(SuccessMessageMixin, CreateView):
    """Create a customer account, then hand off to the login page.

    New users sign in themselves — auto-login after signup is left as a
    student exercise.
    """

    form_class = SignupForm
    template_name = "accounts/signup.html"
    success_url = reverse_lazy("accounts:login")
    success_message = "Account created — you can now sign in."


class SignInView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = SignInForm


class SignOutView(LogoutView):
    def post(self, request, *args, **kwargs):
        # Flash after super() has flushed the session, or the message
        # would be wiped along with it.
        response = super().post(request, *args, **kwargs)
        messages.info(request, "You have signed out.")
        return response


class SecurityCenterView(LoginRequiredMixin, TemplateView):
    """Account Security Center dashboard."""

    template_name = "accounts/security_center.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context["two_factor_enabled"] = getattr(
            user, "totp_device", None
        ) is not None and getattr(user.totp_device, "is_confirmed", False)
        context["password_set"] = user.has_usable_password()
        context["active_session_count"] = 1
        return context


class PasswordChangeView(
    LoginRequiredMixin, SuccessMessageMixin, AuthPasswordChangeView
):
    """Step-up password rotation requiring current password verification."""

    form_class = PasswordChangeForm
    template_name = "accounts/password_change.html"
    success_url = reverse_lazy("accounts:security_center")
    success_message = "Your password has been changed successfully."

    def form_valid(self, form):
        response = super().form_valid(form)
        user = self.request.user
        if user.email:
            send_mail(
                subject="Security Alert: Password Changed",
                message=(
                    f"Hello {user.username},\n\n"
                    "Your ThoughtTronix account password was changed successfully.\n\n"
                    "If you did not perform this change, please contact our security team immediately.\n\n"
                    "— The ThoughtTronix Security Team"
                ),
                from_email=None,
                recipient_list=[user.email],
                fail_silently=False,
            )
        return response


class AddressListView(LoginRequiredMixin, ListView):
    """The customer's address book."""

    template_name = "accounts/address_list.html"
    context_object_name = "addresses"

    def get_queryset(self):
        return Address.objects.filter(user=self.request.user)


class AddressCreateView(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    """Add a new address to the address book."""

    form_class = AddressForm
    template_name = "accounts/address_form.html"
    success_url = reverse_lazy("accounts:address_list")
    success_message = "Address saved."

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)


class AddressUpdateView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    """Edit an existing saved address."""

    form_class = AddressForm
    template_name = "accounts/address_form.html"
    success_url = reverse_lazy("accounts:address_list")
    success_message = "Address updated."

    def get_queryset(self):
        return Address.objects.filter(user=self.request.user)


class AddressDeleteView(LoginRequiredMixin, SuccessMessageMixin, DeleteView):
    """Delete a saved address with fallback for default statuses."""

    template_name = "accounts/address_confirm_delete.html"
    context_object_name = "address"
    success_url = reverse_lazy("accounts:address_list")
    success_message = "Address removed."

    def get_queryset(self):
        return Address.objects.filter(user=self.request.user)

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, self.success_message)
        return super().delete(request, *args, **kwargs)


class SetDefaultAddressView(LoginRequiredMixin, View):
    """POST-only: set a saved address as default shipping, billing, or both."""

    def post(self, request, pk):
        address = get_object_or_404(Address, pk=pk, user=request.user)
        target = request.POST.get("target")

        if target == "shipping":
            address.is_default_shipping = True
            address.save()
            messages.success(
                request,
                f"'{address.label or address.name}' is now your default shipping address.",
            )
        elif target == "billing":
            address.is_default_billing = True
            address.save()
            messages.success(
                request,
                f"'{address.label or address.name}' is now your default billing address.",
            )
        elif target == "both":
            address.is_default_shipping = True
            address.is_default_billing = True
            address.save()
            messages.success(
                request,
                f"'{address.label or address.name}' is now your default shipping and billing address.",
            )
        else:
            messages.error(request, "Invalid default address selection.")

        return redirect("accounts:address_list")
