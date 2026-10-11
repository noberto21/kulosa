from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator

from .forms import (
    LoginForm, ProfileForm, RegisterForm, ResetConfirmForm, ResetRequestForm, StyledPasswordChangeForm,
)
from .ratelimit import rate_limit


@rate_limit("register", limit=10, window=3600)
def register(request):
    if request.user.is_authenticated:
        return redirect("accounts:account")
    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        messages.success(request, f"Welcome to KULOSA, {user.get_short_name()}.")
        return redirect("accounts:account")
    return render(request, "accounts/register.html", {"form": form})


@method_decorator(rate_limit("login", limit=10, window=300), name="dispatch")
class KulosaLoginView(auth_views.LoginView):
    form_class = LoginForm
    template_name = "accounts/login.html"
    redirect_authenticated_user = True


class KulosaLogoutView(auth_views.LogoutView):
    """POST-only (Django 5). The header renders a CSRF-protected form."""

    def post(self, request, *args, **kwargs):
        messages.info(request, "You've been logged out.")
        return super().post(request, *args, **kwargs)


@method_decorator(rate_limit("pwreset", limit=5, window=3600), name="dispatch")
class KulosaPasswordResetView(auth_views.PasswordResetView):
    form_class = ResetRequestForm
    template_name = "accounts/password_reset_form.html"
    email_template_name = "accounts/password_reset_email.txt"
    subject_template_name = "accounts/password_reset_subject.txt"
    success_url = reverse_lazy("accounts:password_reset_done")


class KulosaPasswordResetDoneView(auth_views.PasswordResetDoneView):
    template_name = "accounts/password_reset_done.html"


class KulosaPasswordResetConfirmView(auth_views.PasswordResetConfirmView):
    form_class = ResetConfirmForm
    template_name = "accounts/password_reset_confirm.html"
    success_url = reverse_lazy("accounts:password_reset_complete")


class KulosaPasswordResetCompleteView(auth_views.PasswordResetCompleteView):
    template_name = "accounts/password_reset_complete.html"


@login_required
def account(request):
    return render(request, "accounts/account.html")


@login_required
def profile_edit(request):
    form = ProfileForm(request.POST or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Profile updated.")
        return redirect("accounts:account")
    return render(request, "accounts/profile_form.html", {"form": form})


class KulosaPasswordChangeView(auth_views.PasswordChangeView):
    form_class = StyledPasswordChangeForm
    template_name = "accounts/password_change.html"
    success_url = reverse_lazy("accounts:account")

    def form_valid(self, form):
        messages.success(self.request, "Password changed.")
        return super().form_valid(form)
