import os
import shutil
import tempfile
from datetime import timedelta
from io import BytesIO
from unittest import mock

from django.contrib.admin.sites import site as admin_site
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from . import images, workflow
from .admin import EventAdminForm
from .constants import KENYA_COUNTIES
from .forms import EventForm
from .models import Category, Event, OrganizerProfile
from .notifications import send_review_result

User = get_user_model()
FMT = "%Y-%m-%dT%H:%M"
MEDIA = tempfile.mkdtemp(prefix="kulosa-test-media-")


def tearDownModule():
    shutil.rmtree(MEDIA, ignore_errors=True)


def image_bytes(fmt="PNG", size=(300, 200), exif=False):
    img = Image.new("RGB", size, (200, 80, 30))
    buf = BytesIO()
    if exif and fmt == "JPEG":
        ex = Image.Exif()
        ex[0x010F] = "SecretCameraMaker"
        img.save(buf, fmt, exif=ex)
    else:
        img.save(buf, fmt)
    return buf.getvalue()


def upload(name="poster.png", data=None, ctype="image/png"):
    return SimpleUploadedFile(name, data if data is not None else image_bytes(), content_type=ctype)


@override_settings(MEDIA_ROOT=MEDIA)
class Base(TestCase):
    def setUp(self):
        cache.clear()
        self.cat = Category.objects.create(name="Sports", slug="sports")
        self.owner = User.objects.create_user("owner@example.com", "pw-Owner-1234", full_name="Owner One")
        self.other = User.objects.create_user("other@example.com", "pw-Other-1234", full_name="Other Two")
        self.staff = User.objects.create_superuser("staff@example.com", "pw-Staff-1234", full_name="Staff Person")
        self.start = timezone.now() + timedelta(days=5)

    def data(self, **kw):
        d = {
            "title": "Lakeside Fun Run", "summary": "A friendly 5K by the lake.",
            "description": "Bring water and good shoes.", "category": self.cat.pk,
            "start_datetime": timezone.localtime(self.start).strftime(FMT),
            "end_datetime": timezone.localtime(self.start + timedelta(hours=3)).strftime(FMT),
            "event_type": "PHYSICAL", "venue_name": "Lakefront", "address": "Beach Rd", "county": "Kisumu",
            "town": "Kisumu", "is_free": "on", "booking_url": "", "action": "draft",
        }
        d.update(kw)
        return {k: v for k, v in d.items() if v is not None}

    def make_event(self, owner=None, **kw):
        base = dict(title="Fun Run", summary="s", description="d", category=self.cat, owner=owner or self.owner,
                    start_datetime=self.start, end_datetime=self.start + timedelta(hours=2),
                    venue_name="Park", town="Kisumu", county="Kisumu", is_free=True)
        base.update(kw)
        return Event.objects.create(**base)

    def login(self, user=None):
        self.client.force_login(user or self.owner)


# ---------------------------------------------------------------- images
class ImageSafetyTests(Base):
    def test_valid_png_accepted_and_renamed(self):
        out = images.clean_image_upload(upload("My Party Poster (final).PNG"))
        self.assertRegex(out.name, r"^[0-9a-f]{32}\.png$")
        Image.open(out).verify()

    def test_exif_metadata_stripped(self):
        src = upload("p.jpg", image_bytes("JPEG", exif=True), "image/jpeg")
        self.assertIn(0x010F, Image.open(BytesIO(src.read())).getexif())
        src.seek(0)
        out = images.clean_image_upload(src)
        self.assertEqual(len(Image.open(out).getexif()), 0)

    def test_svg_disguised_as_jpg_rejected(self):
        svg = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
        form = EventForm(self.data(), {"cover_image": upload("poster.jpg", svg, "image/jpeg")}, user=self.owner)
        self.assertIn("cover_image", form.errors)

    def test_text_file_rejected(self):
        form = EventForm(self.data(), {"cover_image": upload("poster.png", b"not an image at all")}, user=self.owner)
        self.assertIn("cover_image", form.errors)

    def test_gif_rejected(self):
        form = EventForm(self.data(), {"cover_image": upload("a.gif", image_bytes("GIF"), "image/gif")}, user=self.owner)
        self.assertIn("cover_image", form.errors)

    def test_oversize_rejected(self):
        with mock.patch.object(images, "MAX_BYTES", 100):
            form = EventForm(self.data(), {"cover_image": upload()}, user=self.owner)
            self.assertIn("MB", " ".join(form.errors["cover_image"]))

    def test_huge_dimensions_rejected(self):
        with mock.patch.object(images, "MAX_DIMENSION", 100):
            form = EventForm(self.data(), {"cover_image": upload()}, user=self.owner)
            self.assertIn("too large", " ".join(form.errors["cover_image"]))

    def test_webp_and_jpeg_accepted(self):
        for fmt, name, ctype in [("WEBP", "a.webp", "image/webp"), ("JPEG", "a.jpg", "image/jpeg")]:
            form = EventForm(self.data(), {"cover_image": upload(name, image_bytes(fmt), ctype)}, user=self.owner)
            self.assertNotIn("cover_image", form.errors, fmt)


# ---------------------------------------------------------------- form validation
class EventFormTests(Base):
    def form(self, **kw):
        return EventForm(self.data(**kw), user=self.owner)

    def test_valid(self):
        self.assertTrue(self.form().is_valid(), self.form().errors)

    def test_end_before_start(self):
        f = self.form(end_datetime=timezone.localtime(self.start - timedelta(hours=1)).strftime(FMT))
        self.assertIn("end_datetime", f.errors)

    def test_paid_needs_price(self):
        f = self.form(is_free=None, ticket_price="")
        self.assertIn("ticket_price", f.errors)

    def test_negative_price_rejected(self):
        self.assertIn("ticket_price", self.form(is_free=None, ticket_price="-5").errors)

    def test_free_event_discards_price(self):
        f = self.form(ticket_price="500")
        self.assertTrue(f.is_valid())
        self.assertIsNone(f.save(commit=False).ticket_price)

    def test_county_must_be_real(self):
        self.assertIn("county", self.form(county="Narnia").errors)
        self.assertEqual(len(KENYA_COUNTIES), 47)

    def test_booking_url_schemes(self):
        for bad in ["javascript:alert(1)", "ftp://example.com/x", "data:text/html,hi"]:
            self.assertIn("booking_url", self.form(booking_url=bad).errors, bad)
        bare = self.form(booking_url="example.com")  # Django assumes a scheme for bare domains
        self.assertTrue(bare.is_valid())
        self.assertTrue(bare.cleaned_data["booking_url"].startswith(("http://", "https://")))
        self.assertNotIn("booking_url", self.form(booking_url="https://tickets.example.com/e/1").errors)

    def test_in_person_needs_a_place_but_online_does_not(self):
        self.assertTrue(self.form(venue_name="", address="").errors)
        self.assertTrue(self.form(event_type="ONLINE", venue_name="", address="", county="", town="").is_valid())

    def test_submitting_a_past_event_is_blocked_but_drafting_is_not(self):
        past = timezone.localtime(timezone.now() - timedelta(days=3))
        kw = dict(start_datetime=(past - timedelta(hours=2)).strftime(FMT), end_datetime=past.strftime(FMT))
        self.assertTrue(self.form(action="draft", **kw).is_valid())
        self.assertIn("end_datetime", self.form(action="submit", **kw).errors)

    def test_organizer_choices_limited_to_own(self):
        mine = OrganizerProfile.objects.create(owner=self.owner, name="Mine")
        theirs = OrganizerProfile.objects.create(owner=self.other, name="Theirs")
        f = self.form(organizer=theirs.pk)
        self.assertIn("organizer", f.errors)
        self.assertTrue(self.form(organizer=mine.pk).is_valid())

    def test_no_organizer_field_without_profile(self):
        self.assertNotIn("organizer", self.form().fields)


# ---------------------------------------------------------------- workflow
class WorkflowTests(Base):
    def test_submit_sets_pending_and_timestamp(self):
        e = self.make_event(status="DRAFT")
        workflow.submit_for_review(e)
        e.refresh_from_db()
        self.assertEqual(e.status, "PENDING")
        self.assertIsNotNone(e.submitted_at)

    def test_cannot_submit_past_event(self):
        e = self.make_event(status="DRAFT", start_datetime=timezone.now() - timedelta(days=2), end_datetime=timezone.now() - timedelta(days=1))
        with self.assertRaises(ValidationError):
            workflow.submit_for_review(e)

    def test_invalid_transitions_raise(self):
        pub = self.make_event(status="PUBLISHED")
        with self.assertRaises(workflow.InvalidTransition):
            workflow.submit_for_review(pub)
        with self.assertRaises(workflow.InvalidTransition):
            workflow.approve(pub, self.staff)
        draft = self.make_event(status="DRAFT", title="D")
        with self.assertRaises(workflow.InvalidTransition):
            workflow.cancel(draft, self.owner)

    def test_approve_records_reviewer(self):
        e = self.make_event(status="PENDING")
        workflow.approve(e, self.staff)
        e.refresh_from_db()
        self.assertEqual((e.status, e.reviewed_by), ("PUBLISHED", self.staff))
        self.assertIsNotNone(e.reviewed_at)

    def test_reject_needs_note(self):
        e = self.make_event(status="PENDING")
        with self.assertRaises(ValidationError):
            workflow.reject(e, self.staff, "   ")
        workflow.reject(e, self.staff, "Poster is blurry.")
        e.refresh_from_db()
        self.assertEqual((e.status, e.moderation_note), ("REJECTED", "Poster is blurry."))

    def test_resubmit_clears_old_review(self):
        e = self.make_event(status="PENDING")
        workflow.reject(e, self.staff, "Fix the date.")
        workflow.submit_for_review(e)
        e.refresh_from_db()
        self.assertEqual((e.status, e.moderation_note, e.reviewed_by), ("PENDING", "", None))

    def test_complete_past_events_command(self):
        old = self.make_event(status="PUBLISHED", title="Old", start_datetime=timezone.now() - timedelta(days=3), end_datetime=timezone.now() - timedelta(days=2))
        upcoming = self.make_event(status="PUBLISHED", title="Soon")
        pending_old = self.make_event(status="PENDING", title="PO", start_datetime=timezone.now() - timedelta(days=3), end_datetime=timezone.now() - timedelta(days=2))
        call_command("complete_past_events", verbosity=0)
        for e in (old, upcoming, pending_old):
            e.refresh_from_db()
        self.assertEqual((old.status, upcoming.status, pending_old.status), ("COMPLETED", "PUBLISHED", "PENDING"))


# ---------------------------------------------------------------- views
class DashboardViewTests(Base):
    def test_login_required_everywhere(self):
        e = self.make_event()
        for name, args in [("list", []), ("create", []), ("organizer", []), ("edit", [e.pk])]:
            r = self.client.get(reverse(f"dashboard:{name}", args=args))
            self.assertEqual(r.status_code, 302, name)
            self.assertIn("/login/", r["Location"])
        for name in ["submit", "withdraw", "cancel", "delete"]:
            r = self.client.post(reverse(f"dashboard:{name}", args=[e.pk]))
            self.assertIn("/login/", r["Location"], name)

    def test_share_event_link_leads_to_create_form_after_login(self):
        self.login()
        r = self.client.get(reverse("core:share_event"), follow=True)
        self.assertEqual(r.redirect_chain[-1][0], reverse("dashboard:create"))
        self.assertContains(r, "Share an event")

    def test_create_draft(self):
        self.login()
        r = self.client.post(reverse("dashboard:create"), self.data(action="draft"))
        self.assertRedirects(r, reverse("dashboard:list"))
        e = Event.objects.get()
        self.assertEqual((e.status, e.owner, e.title), ("DRAFT", self.owner, "Lakeside Fun Run"))

    def test_create_and_submit(self):
        self.login()
        self.client.post(reverse("dashboard:create"), self.data(action="submit"))
        e = Event.objects.get()
        self.assertEqual(e.status, "PENDING")
        self.assertIsNotNone(e.submitted_at)

    def test_cannot_spoof_status_owner_or_review_fields(self):
        self.login()
        self.client.post(reverse("dashboard:create"), self.data(action="draft", status="PUBLISHED", owner=self.other.pk,
                                                                is_featured="on", reviewed_by=self.staff.pk))
        e = Event.objects.get()
        self.assertEqual((e.status, e.owner, e.is_featured, e.reviewed_by), ("DRAFT", self.owner, False, None))

    def test_invalid_post_shows_errors_and_saves_nothing(self):
        self.login()
        r = self.client.post(reverse("dashboard:create"), self.data(title=""))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "This field is required")
        self.assertEqual(Event.objects.count(), 0)

    def test_poster_upload_saved_with_random_name(self):
        self.login()
        self.client.post(reverse("dashboard:create"), {**self.data(), "cover_image": upload("../../evil name.png")})
        e = Event.objects.get()
        self.assertRegex(e.cover_image.name, r"^events/posters/[0-9a-f]{32}\.png$")
        self.assertTrue(os.path.exists(e.cover_image.path))

    def test_replacing_poster_deletes_old_file(self):
        self.login()
        e = self.make_event(status="DRAFT")
        e.cover_image.save("x.png", upload(), save=True)
        old = e.cover_image.path
        self.client.post(reverse("dashboard:edit", args=[e.pk]), {**self.data(), "cover_image": upload("n.png", image_bytes(size=(320, 220)))})
        e.refresh_from_db()
        self.assertFalse(os.path.exists(old))
        self.assertTrue(os.path.exists(e.cover_image.path))

    def test_others_events_are_404_for_every_action(self):
        e = self.make_event(owner=self.other, status="DRAFT")
        self.login()
        self.assertEqual(self.client.get(reverse("dashboard:edit", args=[e.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("dashboard:edit", args=[e.pk]), self.data(title="Hijack")).status_code, 404)
        for name in ["submit", "withdraw", "cancel", "delete"]:
            self.assertEqual(self.client.post(reverse(f"dashboard:{name}", args=[e.pk])).status_code, 404, name)
        e.refresh_from_db()
        self.assertEqual((e.title, e.status), ("Fun Run", "DRAFT"))

    def test_action_endpoints_reject_get(self):
        e = self.make_event(status="DRAFT")
        self.login()
        for name in ["submit", "withdraw", "cancel", "delete"]:
            self.assertEqual(self.client.get(reverse(f"dashboard:{name}", args=[e.pk])).status_code, 405, name)

    def test_csrf_enforced_on_actions(self):
        from django.test import Client
        e = self.make_event(status="DRAFT")
        c = Client(enforce_csrf_checks=True)
        c.force_login(self.owner)
        self.assertEqual(c.post(reverse("dashboard:delete", args=[e.pk])).status_code, 403)
        self.assertTrue(Event.objects.filter(pk=e.pk).exists())

    def test_editing_published_event_returns_it_to_review(self):
        e = self.make_event(status="PUBLISHED", title="Lakeside Fun Run", summary="A friendly 5K by the lake.",
                            description="Bring water and good shoes.", venue_name="Lakefront", address="Beach Rd")
        e.start_datetime, e.end_datetime = self.start.replace(second=0, microsecond=0), (self.start + timedelta(hours=3)).replace(second=0, microsecond=0)
        e.save()
        self.login()
        self.client.post(reverse("dashboard:edit", args=[e.pk]), self.data(action="save", title="Lakeside Fun Run 2"))
        e.refresh_from_db()
        self.assertEqual((e.status, e.title), ("PENDING", "Lakeside Fun Run 2"))

    def test_saving_published_event_without_changes_keeps_it_published(self):
        e = self.make_event(status="PUBLISHED", title="Lakeside Fun Run", summary="A friendly 5K by the lake.",
                            description="Bring water and good shoes.", venue_name="Lakefront", address="Beach Rd")
        e.start_datetime, e.end_datetime = self.start.replace(second=0, microsecond=0), (self.start + timedelta(hours=3)).replace(second=0, microsecond=0)
        e.save()
        self.login()
        self.client.post(reverse("dashboard:edit", args=[e.pk]), self.data(action="save"))
        e.refresh_from_db()
        self.assertEqual(e.status, "PUBLISHED")

    def test_cancelled_and_completed_cannot_be_edited(self):
        self.login()
        for s in ("CANCELLED", "COMPLETED"):
            e = self.make_event(status=s, title=s)
            r = self.client.post(reverse("dashboard:edit", args=[e.pk]), self.data(title="Changed"))
            self.assertRedirects(r, reverse("dashboard:list"))
            e.refresh_from_db()
            self.assertEqual(e.title, s)

    def test_rejected_event_can_be_fixed_and_resubmitted(self):
        e = self.make_event(status="REJECTED", moderation_note="Add a venue.")
        self.login()
        r = self.client.get(reverse("dashboard:edit", args=[e.pk]))
        self.assertContains(r, "Add a venue.")
        self.client.post(reverse("dashboard:edit", args=[e.pk]), self.data(action="submit"))
        e.refresh_from_db()
        self.assertEqual((e.status, e.moderation_note), ("PENDING", ""))

    def test_withdraw_cancel_delete_rules(self):
        self.login()
        pending = self.make_event(status="PENDING", title="P")
        self.client.post(reverse("dashboard:withdraw", args=[pending.pk]))
        pending.refresh_from_db()
        self.assertEqual(pending.status, "DRAFT")

        pub = self.make_event(status="PUBLISHED", title="Pub")
        self.client.post(reverse("dashboard:delete", args=[pub.pk]))
        self.assertTrue(Event.objects.filter(pk=pub.pk).exists())  # can't delete live events
        self.client.post(reverse("dashboard:cancel", args=[pub.pk]))
        pub.refresh_from_db()
        self.assertEqual(pub.status, "CANCELLED")

        draft = self.make_event(status="DRAFT", title="Dr")
        self.client.post(reverse("dashboard:cancel", args=[draft.pk]))
        draft.refresh_from_db()
        self.assertEqual(draft.status, "DRAFT")  # drafts can't be "cancelled"
        self.client.post(reverse("dashboard:delete", args=[draft.pk]))
        self.assertFalse(Event.objects.filter(pk=draft.pk).exists())

    def test_deleting_draft_removes_poster_file(self):
        e = self.make_event(status="DRAFT")
        e.cover_image.save("x.png", upload(), save=True)
        path = e.cover_image.path
        self.login()
        self.client.post(reverse("dashboard:delete", args=[e.pk]))
        self.assertFalse(os.path.exists(path))

    def test_dashboard_shows_only_own_events_and_filters(self):
        self.make_event(title="Mine draft", status="DRAFT")
        self.make_event(title="Mine pending", status="PENDING")
        self.make_event(title="Theirs", owner=self.other, status="DRAFT")
        self.login()
        r = self.client.get(reverse("dashboard:list"))
        self.assertContains(r, "Mine draft")
        self.assertContains(r, "Mine pending")
        self.assertNotContains(r, "Theirs")
        r = self.client.get(reverse("dashboard:list") + "?status=PENDING")
        self.assertContains(r, "Mine pending")
        self.assertNotContains(r, "Mine draft")
        self.assertEqual(self.client.get(reverse("dashboard:list") + "?status=bogus").status_code, 200)

    def test_html_in_titles_is_escaped(self):
        self.make_event(title="<script>alert(1)</script>", status="DRAFT")
        self.login()
        r = self.client.get(reverse("dashboard:list"))
        self.assertNotContains(r, "<script>alert(1)</script>")
        self.assertContains(r, "&lt;script&gt;")


class OrganizerAndProfileTests(Base):
    def test_create_then_update_organizer_profile(self):
        self.login()
        r = self.client.post(reverse("dashboard:organizer"), {"name": "Lake Events", "website": "https://lake.example.com"})
        self.assertRedirects(r, reverse("dashboard:list"))
        p = OrganizerProfile.objects.get(owner=self.owner)
        self.assertEqual((p.slug, p.is_verified), ("lake-events", False))
        self.client.post(reverse("dashboard:organizer"), {"name": "Lake Events Ltd", "is_verified": "on"})
        p.refresh_from_db()
        self.assertEqual(OrganizerProfile.objects.filter(owner=self.owner).count(), 1)
        self.assertEqual((p.name, p.is_verified), ("Lake Events Ltd", False))  # users can't self-verify

    def test_organizer_website_scheme_checked(self):
        self.login()
        r = self.client.post(reverse("dashboard:organizer"), {"name": "X", "website": "javascript:alert(1)"})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(OrganizerProfile.objects.exists())

    def test_profile_edit_and_phone_validation(self):
        self.login()
        r = self.client.post(reverse("accounts:profile_edit"), {"full_name": "New Name", "phone": "abc"})
        self.assertEqual(r.status_code, 200)
        r = self.client.post(reverse("accounts:profile_edit"), {"full_name": "New Name", "phone": "0712 345 678"})
        self.assertRedirects(r, reverse("accounts:account"))
        self.owner.refresh_from_db()
        self.assertEqual((self.owner.full_name, self.owner.phone), ("New Name", "0712 345 678"))

    def test_password_change(self):
        self.login()
        r = self.client.post(reverse("accounts:password_change"), {
            "old_password": "pw-Owner-1234", "new_password1": "Zebra-Plains-8841", "new_password2": "Zebra-Plains-8841"})
        self.assertRedirects(r, reverse("accounts:account"))
        self.owner.refresh_from_db()
        self.assertTrue(self.owner.check_password("Zebra-Plains-8841"))


# ---------------------------------------------------------------- admin + email
class AdminModerationTests(Base):
    def changelist_action(self, action, events):
        self.client.force_login(self.staff)
        return self.client.post(reverse("admin:events_event_changelist"), {
            "action": action, "_selected_action": [e.pk for e in events]}, follow=True)

    def test_approve_action_publishes_pending_only_and_emails_owner(self):
        pending = self.make_event(status="PENDING", title="P")
        draft = self.make_event(status="DRAFT", title="D")
        r = self.changelist_action("approve_selected", [pending, draft])
        pending.refresh_from_db(); draft.refresh_from_db()
        self.assertEqual((pending.status, pending.reviewed_by, draft.status), ("PUBLISHED", self.staff, "DRAFT"))
        self.assertContains(r, "skipped")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["owner@example.com"])
        self.assertIn("approved", mail.outbox[0].body)

    def test_cancel_action(self):
        pub = self.make_event(status="PUBLISHED")
        self.changelist_action("cancel_selected", [pub])
        pub.refresh_from_db()
        self.assertEqual(pub.status, "CANCELLED")

    def test_non_staff_cannot_reach_admin_actions(self):
        e = self.make_event(status="PENDING")
        self.client.force_login(self.owner)
        r = self.client.post(reverse("admin:events_event_changelist"), {"action": "approve_selected", "_selected_action": [e.pk]})
        self.assertEqual(r.status_code, 302)
        e.refresh_from_db()
        self.assertEqual(e.status, "PENDING")

    def test_admin_form_requires_reason_to_reject(self):
        e = self.make_event(status="PENDING")
        form = EventAdminForm({"status": "REJECTED", "moderation_note": " "}, instance=e)
        form.is_valid()
        self.assertIn("moderation_note", form.errors)

    def test_admin_status_edit_sets_reviewer_and_emails_rejection(self):
        e = self.make_event(status="PENDING")
        model_admin = admin_site._registry[Event]
        e.status, e.moderation_note = "REJECTED", "Please add a clearer poster."
        form = mock.Mock(changed_data=["status", "moderation_note"])
        request = mock.Mock(user=self.staff)
        model_admin.save_model(request, e, form, change=True)
        e.refresh_from_db()
        self.assertEqual((e.status, e.reviewed_by), ("REJECTED", self.staff))
        self.assertIn("Please add a clearer poster.", mail.outbox[-1].body)

    def test_mail_failure_never_blocks_moderation(self):
        e = self.make_event(status="PENDING")
        with mock.patch("apps.events.notifications.send_mail", side_effect=OSError("smtp down")):
            workflow.approve(e, self.staff)
            self.assertFalse(send_review_result(e))
        e.refresh_from_db()
        self.assertEqual(e.status, "PUBLISHED")
