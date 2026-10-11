from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import (
    AuthenticationForm, PasswordResetForm, SetPasswordForm, UserCreationForm,
)

User = get_user_model()


class StyledFormMixin:
    """Apply the site's Tailwind `.field` class to every widget."""

    def _style(self):
        for field in self.fields.values():
            existing = field.widget.attrs.get("class", "")
            css = "h-4 w-4 rounded border-navy-900/30" if isinstance(field.widget, forms.CheckboxInput) else "field"
            field.widget.attrs["class"] = f"{existing} {css}".strip()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style()


class RegisterForm(StyledFormMixin, UserCreationForm):
    class Meta:
        model = User
        fields = ("full_name", "email", "phone")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["full_name"].label = "Full name"
        self.fields["email"].widget.attrs.update({"autocomplete": "email"})
        self.fields["email"].widget.attrs.pop("autofocus", None)
        self.fields["full_name"].widget.attrs.update({"autocomplete": "name", "autofocus": True})
        self.fields["phone"].widget.attrs.update({"autocomplete": "tel", "placeholder": "e.g. 0712 345 678"})
        self.fields["phone"].required = False
        self.fields["password1"].widget.attrs["autocomplete"] = "new-password"
        self.fields["password2"].widget.attrs["autocomplete"] = "new-password"

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists. Try logging in instead.")
        return email


class LoginForm(StyledFormMixin, AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Email"
        self.fields["username"].widget = forms.EmailInput(attrs={"class": "field"})
        self.fields["username"].widget.attrs.update({"autocomplete": "email", "autofocus": True})
        self.fields["password"].widget.attrs["autocomplete"] = "current-password"
        self.error_messages = {
            **self.error_messages,
            "invalid_login": "That email and password don't match an active account. Check both and try again.",
        }


class ResetRequestForm(StyledFormMixin, PasswordResetForm):
    pass


class ResetConfirmForm(StyledFormMixin, SetPasswordForm):
    pass


from django.contrib.auth.forms import PasswordChangeForm  # noqa: E402


class ProfileForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = User
        fields = ("full_name", "phone")
        labels = {"full_name": "Full name", "phone": "Phone number"}

    def clean_phone(self):
        phone = (self.cleaned_data.get("phone") or "").strip()
        digits = phone.replace(" ", "").replace("-", "")
        if phone and not (digits.lstrip("+").isdigit() and 9 <= len(digits.lstrip("+")) <= 15):
            raise forms.ValidationError("Enter a phone number with 9 to 15 digits, for example 0712 345 678.")
        return phone


class StyledPasswordChangeForm(StyledFormMixin, PasswordChangeForm):
    pass
