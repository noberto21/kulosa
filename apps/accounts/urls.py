from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("register/", views.register, name="register"),
    path("login/", views.KulosaLoginView.as_view(), name="login"),
    path("logout/", views.KulosaLogoutView.as_view(), name="logout"),
    path("account/", views.account, name="account"),
    path("account/edit/", views.profile_edit, name="profile_edit"),
    path("account/password/", views.KulosaPasswordChangeView.as_view(), name="password_change"),
    path("password-reset/", views.KulosaPasswordResetView.as_view(), name="password_reset"),
    path("password-reset/sent/", views.KulosaPasswordResetDoneView.as_view(), name="password_reset_done"),
    path("password-reset/<uidb64>/<token>/", views.KulosaPasswordResetConfirmView.as_view(), name="password_reset_confirm"),
    path("password-reset/complete/", views.KulosaPasswordResetCompleteView.as_view(), name="password_reset_complete"),
]
