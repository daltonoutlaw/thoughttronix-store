from importlib import import_module

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth import login as auth_login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import (
    LoginView,
    LogoutView,
)
from django.contrib.auth.views import (
    PasswordChangeView as AuthPasswordChangeView,
)
from django.contrib.messages.views import SuccessMessageMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View
from django.views.generic import (
    CreateView,
    DeleteView,
    ListView,
    TemplateView,
    UpdateView,
)

from .audit import record_security_event
from .forms import (
    AddressForm,
    PasswordChangeForm,
    PasswordConfirmForm,
    SignInForm,
    SignupForm,
    TOTPVerifyForm,
    TwoFactorChallengeForm,
)
from .models import Address, BackupCode, SecurityEvent, TOTPDevice, UserSession
from .rate_limit import (
    clear_rate_limit,
    get_client_ip,
    is_rate_limited,
    record_failure,
)


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

    def post(self, request, *args, **kwargs):
        ip = get_client_ip(request)
        rate_key = f"ratelimit:login:{ip}"
        if is_rate_limited(rate_key, max_attempts=5):
            form = self.get_form()
            form.add_error(
                None,
                "Too many failed login attempts. Please try again in 5 minutes.",
            )
            return self.form_invalid(form)
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        ip = get_client_ip(self.request)
        rate_key = f"ratelimit:login:{ip}"
        clear_rate_limit(rate_key)

        user = form.get_user()
        if getattr(user, "totp_device", None) and user.totp_device.is_confirmed:
            self.request.session["stage_2fa_user_id"] = user.pk
            self.request.session["stage_2fa_next"] = self.get_redirect_url() or ""
            return redirect("accounts:two_factor_challenge")

        record_security_event(
            user,
            SecurityEvent.EventType.LOGIN_SUCCESS,
            request=self.request,
        )
        return super().form_valid(form)

    def form_invalid(self, form):
        ip = get_client_ip(self.request)
        rate_key = f"ratelimit:login:{ip}"
        record_failure(rate_key, timeout=300)

        username = form.data.get("username")
        if username:
            attempted_user = get_user_model().objects.filter(username=username).first()
            if attempted_user:
                record_security_event(
                    attempted_user,
                    SecurityEvent.EventType.LOGIN_FAILED,
                    request=self.request,
                )
        return super().form_invalid(form)


class TwoFactorChallengeView(View):
    """Secondary authentication challenge screen for accounts with active 2FA."""

    template_name = "accounts/two_factor_challenge.html"

    def get_user(self, request):
        if request.user.is_authenticated:
            return None
        user_id = request.session.get("stage_2fa_user_id")
        if not user_id:
            return None
        return get_user_model().objects.filter(pk=user_id, is_active=True).first()

    def get(self, request):
        if request.user.is_authenticated:
            return redirect("products:catalog")
        user = self.get_user(request)
        if not user:
            return redirect("accounts:login")

        form = TwoFactorChallengeForm(user=user)
        return render(request, self.template_name, {"form": form})

    def post(self, request):
        if request.user.is_authenticated:
            return redirect("products:catalog")
        user = self.get_user(request)
        if not user:
            return redirect("accounts:login")

        ip = get_client_ip(request)
        rate_key = f"ratelimit:2fa:{ip}:{user.pk}"

        if is_rate_limited(rate_key, max_attempts=5):
            form = TwoFactorChallengeForm(user=user, data=request.POST)
            form.add_error(
                None,
                "Too many failed verification attempts. Please try again in 5 minutes.",
            )
            return render(request, self.template_name, {"form": form})

        form = TwoFactorChallengeForm(user=user, data=request.POST)
        if form.is_valid():
            clear_rate_limit(rate_key)
            next_url = request.session.pop("stage_2fa_next", None)
            request.session.pop("stage_2fa_user_id", None)
            auth_login(request, user)
            if getattr(form, "used_backup_code", False):
                record_security_event(
                    user,
                    SecurityEvent.EventType.BACKUP_CODE_USED,
                    request=request,
                    details="Signed in using a single-use backup recovery code",
                )
                messages.info(
                    request,
                    "Signed in using a backup recovery code. This code has now been consumed.",
                )
            record_security_event(
                user,
                SecurityEvent.EventType.LOGIN_SUCCESS,
                request=request,
            )
            if next_url and url_has_allowed_host_and_scheme(
                url=next_url,
                allowed_hosts={request.get_host()},
                require_https=request.is_secure(),
            ):
                return redirect(next_url)
            return redirect("products:catalog")

        record_failure(rate_key, timeout=300)
        record_security_event(
            user,
            SecurityEvent.EventType.LOGIN_FAILED,
            request=request,
            details="Invalid 2FA verification code submitted",
        )
        return render(request, self.template_name, {"form": form})


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
        session_count = user.sessions.count()
        context["active_session_count"] = session_count if session_count > 0 else 1
        context["recent_events"] = user.security_events.all()[:5]
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
        record_security_event(
            self.request.user,
            SecurityEvent.EventType.PASSWORD_CHANGED,
            request=self.request,
        )
        return response


class TwoFactorSetupView(LoginRequiredMixin, View):
    """Initiate TOTP 2FA setup with QR code and manual entry key."""

    template_name = "accounts/two_factor_setup.html"

    def get(self, request):
        if (
            getattr(request.user, "totp_device", None)
            and request.user.totp_device.is_confirmed
        ):
            return redirect("accounts:two_factor_backup_codes")

        totp_device, _ = TOTPDevice.objects.get_or_create(
            user=request.user,
            is_confirmed=False,
        )
        form = TOTPVerifyForm()
        secret_key_formatted = " ".join(
            totp_device.secret_key[i : i + 4]
            for i in range(0, len(totp_device.secret_key), 4)
        )
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "qr_svg": totp_device.qr_code_svg(),
                "secret_key": totp_device.secret_key,
                "secret_key_formatted": secret_key_formatted,
            },
        )


class TwoFactorVerifyView(LoginRequiredMixin, View):
    """Confirm 6-digit TOTP code and activate Two-Factor Authentication."""

    template_name = "accounts/two_factor_setup.html"

    def post(self, request):
        try:
            totp_device = TOTPDevice.objects.get(user=request.user, is_confirmed=False)
        except TOTPDevice.DoesNotExist:
            if (
                getattr(request.user, "totp_device", None)
                and request.user.totp_device.is_confirmed
            ):
                return redirect("accounts:two_factor_backup_codes")
            return redirect("accounts:two_factor_setup")

        form = TOTPVerifyForm(request.POST)
        if form.is_valid():
            code = form.cleaned_data["code"]
            if totp_device.verify_code(code):
                totp_device.is_confirmed = True
                totp_device.save(update_fields=["is_confirmed", "last_used_at"])
                raw_codes = BackupCode.generate_codes(request.user, count=8)
                request.session["raw_backup_codes"] = raw_codes
                record_security_event(
                    request.user,
                    SecurityEvent.EventType.TWO_FACTOR_ENABLED,
                    request=request,
                )
                record_security_event(
                    request.user,
                    SecurityEvent.EventType.BACKUP_CODES_GENERATED,
                    request=request,
                    details="Generated initial set of 8 backup recovery codes",
                )
                messages.success(
                    request,
                    "Two-Factor Authentication is now enabled on your account.",
                )
                return redirect("accounts:two_factor_backup_codes")
            form.add_error(
                "code",
                "Invalid or expired verification code. Please try again.",
            )

        secret_key_formatted = " ".join(
            totp_device.secret_key[i : i + 4]
            for i in range(0, len(totp_device.secret_key), 4)
        )
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "qr_svg": totp_device.qr_code_svg(),
                "secret_key": totp_device.secret_key,
                "secret_key_formatted": secret_key_formatted,
            },
        )


class TwoFactorBackupCodesView(LoginRequiredMixin, View):
    """View and regenerate single-use backup recovery codes."""

    template_name = "accounts/two_factor_backup_codes.html"

    def get(self, request):
        if not (
            getattr(request.user, "totp_device", None)
            and request.user.totp_device.is_confirmed
        ):
            return redirect("accounts:two_factor_setup")

        raw_codes = request.session.pop("raw_backup_codes", None)
        active_codes_count = request.user.backup_codes.filter(is_used=False).count()
        form = PasswordConfirmForm(user=request.user)

        return render(
            request,
            self.template_name,
            {
                "raw_codes": raw_codes,
                "active_codes_count": active_codes_count,
                "form": form,
            },
        )

    def post(self, request):
        if not (
            getattr(request.user, "totp_device", None)
            and request.user.totp_device.is_confirmed
        ):
            return redirect("accounts:two_factor_setup")

        form = PasswordConfirmForm(user=request.user, data=request.POST)
        if form.is_valid():
            raw_codes = BackupCode.generate_codes(request.user, count=8)
            request.session["raw_backup_codes"] = raw_codes
            record_security_event(
                request.user,
                SecurityEvent.EventType.BACKUP_CODES_GENERATED,
                request=request,
                details="Regenerated a fresh set of 8 backup recovery codes",
            )
            messages.success(
                request,
                "New backup recovery codes generated. All previous codes have been invalidated.",
            )
            return redirect("accounts:two_factor_backup_codes")

        active_codes_count = request.user.backup_codes.filter(is_used=False).count()
        return render(
            request,
            self.template_name,
            {
                "raw_codes": None,
                "active_codes_count": active_codes_count,
                "form": form,
            },
        )


class TwoFactorDisableView(LoginRequiredMixin, View):
    """Disable Two-Factor Authentication with step-up password confirmation."""

    template_name = "accounts/two_factor_disable.html"

    def get(self, request):
        if not (
            getattr(request.user, "totp_device", None)
            and request.user.totp_device.is_confirmed
        ):
            return redirect("accounts:security_center")

        form = PasswordConfirmForm(user=request.user)
        return render(request, self.template_name, {"form": form})

    def post(self, request):
        if not (
            getattr(request.user, "totp_device", None)
            and request.user.totp_device.is_confirmed
        ):
            return redirect("accounts:security_center")

        form = PasswordConfirmForm(user=request.user, data=request.POST)
        if form.is_valid():
            TOTPDevice.objects.filter(user=request.user).delete()
            BackupCode.objects.filter(user=request.user).delete()
            record_security_event(
                request.user,
                SecurityEvent.EventType.TWO_FACTOR_DISABLED,
                request=request,
            )
            messages.success(
                request,
                "Two-factor authentication has been disabled.",
            )
            return redirect("accounts:security_center")

        return render(request, self.template_name, {"form": form})


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


class SessionListView(LoginRequiredMixin, ListView):
    """View active browser sessions and connected devices."""

    model = UserSession
    template_name = "accounts/session_list.html"
    context_object_name = "sessions"

    def get_queryset(self):
        return UserSession.objects.filter(user=self.request.user).order_by(
            "-last_activity"
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        current_session_key = self.request.session.session_key
        context["current_session_key"] = current_session_key
        context["other_sessions_count"] = (
            self.get_queryset().exclude(session_key=current_session_key).count()
        )
        return context


class SessionRevokeView(LoginRequiredMixin, View):
    """Revoke a specific secondary user session."""

    def post(self, request, pk):
        session_obj = get_object_or_404(UserSession, pk=pk, user=request.user)

        if session_obj.session_key == request.session.session_key:
            messages.error(
                request, "You cannot revoke your active current session here."
            )
            return redirect("accounts:session_list")

        # Invalidate in Django session storage
        engine = import_module(settings.SESSION_ENGINE)
        session_store = engine.SessionStore(session_key=session_obj.session_key)
        session_store.delete()

        device_name = session_obj.device_type
        ip = session_obj.ip_address
        session_obj.delete()

        record_security_event(
            request.user,
            SecurityEvent.EventType.SESSION_REVOKED,
            request=request,
            details=f"Revoked {device_name} session (IP: {ip or 'Unknown'})",
        )

        messages.success(request, f"Revoked session for {device_name}.")
        return redirect("accounts:session_list")


class SessionRevokeOthersView(LoginRequiredMixin, View):
    """Sign out of all other active sessions across secondary devices."""

    def post(self, request):
        current_key = request.session.session_key
        other_sessions = UserSession.objects.filter(user=request.user).exclude(
            session_key=current_key
        )

        count = other_sessions.count()

        engine = import_module(settings.SESSION_ENGINE)
        for s in other_sessions:
            store = engine.SessionStore(session_key=s.session_key)
            store.delete()

        other_sessions.delete()

        record_security_event(
            request.user,
            SecurityEvent.EventType.ALL_SESSIONS_REVOKED,
            request=request,
            details=f"Signed out {count} secondary session(s)",
        )

        messages.success(
            request, f"Successfully signed out {count} other active session(s)."
        )
        return redirect("accounts:session_list")


class SecurityActivityView(LoginRequiredMixin, ListView):
    """Chronological security audit log and recent activity history."""

    model = SecurityEvent
    template_name = "accounts/security_activity.html"
    context_object_name = "events"
    paginate_by = 20

    def get_queryset(self):
        return SecurityEvent.objects.filter(user=self.request.user).order_by(
            "-created_at"
        )
