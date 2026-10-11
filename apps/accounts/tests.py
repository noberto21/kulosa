from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

User = get_user_model()
GOOD_PW = "Sunrise-Lake-4821"


class UserModelTests(TestCase):
    def test_create_user_normalizes_email(self):
        u = User.objects.create_user("  Ada@Example.COM ", GOOD_PW, full_name="Ada Otieno")
        self.assertEqual(u.email, "ada@example.com")
        self.assertTrue(u.check_password(GOOD_PW))
        self.assertFalse(u.is_staff)

    def test_email_unique_case_insensitive(self):
        User.objects.create_user("ada@example.com", GOOD_PW, full_name="Ada")
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create_user("ADA@example.com", GOOD_PW, full_name="Other")

    def test_superuser_flags(self):
        u = User.objects.create_superuser("root@example.com", GOOD_PW, full_name="Root")
        self.assertTrue(u.is_staff and u.is_superuser)

    def test_email_required(self):
        with self.assertRaises(ValueError):
            User.objects.create_user("", GOOD_PW, full_name="x")


class AuthFlowTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user("ada@example.com", GOOD_PW, full_name="Ada Otieno")

    def test_register_creates_user_and_logs_in(self):
        r = self.client.post(reverse("accounts:register"), {
            "full_name": "Baraka Mwangi", "email": "Baraka@Example.com", "phone": "",
            "password1": GOOD_PW, "password2": GOOD_PW,
        })
        self.assertRedirects(r, reverse("accounts:account"))
        self.assertTrue(User.objects.filter(email="baraka@example.com").exists())
        self.assertIn("_auth_user_id", self.client.session)

    def test_register_rejects_duplicate_email_any_case(self):
        r = self.client.post(reverse("accounts:register"), {
            "full_name": "Dup", "email": "ADA@example.com", "password1": GOOD_PW, "password2": GOOD_PW,
        })
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "already exists")
        self.assertEqual(User.objects.count(), 1)

    def test_register_rejects_weak_password(self):
        r = self.client.post(reverse("accounts:register"), {
            "full_name": "Weak", "email": "weak@example.com", "password1": "12345678", "password2": "12345678",
        })
        self.assertEqual(r.status_code, 200)
        self.assertFalse(User.objects.filter(email="weak@example.com").exists())

    def test_login_with_email_any_case(self):
        r = self.client.post(reverse("accounts:login"), {"username": "ADA@example.com", "password": GOOD_PW})
        self.assertRedirects(r, reverse("accounts:account"))

    def test_login_wrong_password(self):
        r = self.client.post(reverse("accounts:login"), {"username": "ada@example.com", "password": "nope"})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "match an active account")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_inactive_user_cannot_login(self):
        self.user.is_active = False
        self.user.save()
        r = self.client.post(reverse("accounts:login"), {"username": "ada@example.com", "password": GOOD_PW})
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertEqual(r.status_code, 200)

    def test_login_next_is_followed_only_when_safe(self):
        url = reverse("accounts:login")
        r = self.client.post(url + "?next=/events/", {"username": "ada@example.com", "password": GOOD_PW, "next": "/events/"})
        self.assertRedirects(r, "/events/")
        self.client.logout()
        r = self.client.post(url, {"username": "ada@example.com", "password": GOOD_PW, "next": "https://evil.example/"})
        self.assertRedirects(r, reverse("accounts:account"))

    def test_account_requires_login(self):
        r = self.client.get(reverse("accounts:account"))
        self.assertRedirects(r, f"{reverse('accounts:login')}?next={reverse('accounts:account')}")

    def test_logout_requires_post(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("accounts:logout")).status_code, 405)
        self.assertIn("_auth_user_id", self.client.session)
        self.client.post(reverse("accounts:logout"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_csrf_enforced_on_login(self):
        from django.test import Client
        c = Client(enforce_csrf_checks=True)
        r = c.post(reverse("accounts:login"), {"username": "ada@example.com", "password": GOOD_PW})
        self.assertEqual(r.status_code, 403)

    def test_header_shows_logout_when_signed_in(self):
        self.client.force_login(self.user)
        r = self.client.get("/")
        self.assertContains(r, "Log out")
        self.assertNotContains(r, ">Sign Up<")

    def test_login_rate_limited(self):
        url = reverse("accounts:login")
        for _ in range(10):
            self.client.post(url, {"username": "ada@example.com", "password": "bad"})
        r = self.client.post(url, {"username": "ada@example.com", "password": "bad"})
        self.assertEqual(r.status_code, 429)


class PasswordResetTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user("ada@example.com", GOOD_PW, full_name="Ada Otieno")

    def test_reset_email_sent_for_known_and_not_for_unknown_with_same_response(self):
        url = reverse("accounts:password_reset")
        r1 = self.client.post(url, {"email": "ada@example.com"})
        r2 = self.client.post(url, {"email": "ghost@example.com"})
        self.assertRedirects(r1, reverse("accounts:password_reset_done"))
        self.assertRedirects(r2, reverse("accounts:password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("/password-reset/", mail.outbox[0].body)

    def test_full_reset_flow(self):
        self.client.post(reverse("accounts:password_reset"), {"email": "ada@example.com"})
        link = next(l for l in mail.outbox[0].body.splitlines() if "/password-reset/" in l).strip()
        path = link.split("://", 1)[1].split("/", 1)[1]
        r = self.client.get("/" + path, follow=True)  # token redirects to a set-password URL
        self.assertEqual(r.status_code, 200)
        post_url = r.redirect_chain[-1][0]
        new_pw = "Mango-River-7734"
        r = self.client.post(post_url, {"new_password1": new_pw, "new_password2": new_pw})
        self.assertRedirects(r, reverse("accounts:password_reset_complete"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(new_pw))

    def test_bad_token_shows_expired_page(self):
        r = self.client.get(reverse("accounts:password_reset_confirm", args=["MQ", "bad-token"]))
        self.assertContains(r, "expired")
