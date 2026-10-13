from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from .models import Category, Event, EventReport, OrganizerProfile, SavedEvent

User = get_user_model()


class Base(TestCase):
    def setUp(self):
        self.cat = Category.objects.create(name="Sports", slug="sports")
        self.owner = User.objects.create_user("owner@example.com", "pw-Owner-1234", full_name="Owner One")
        self.other = User.objects.create_user("other@example.com", "pw-Other-1234", full_name="Other Two")
        self.staff = User.objects.create_user("staff@example.com", "pw-Staff-1234", full_name="Staff", is_staff=True)
        self.start = timezone.now() + timedelta(days=3)

    def make_event(self, **kw):
        data = dict(title="Fun Run", summary="A run", description="Details", category=self.cat, owner=self.owner,
                    start_datetime=self.start, end_datetime=self.start + timedelta(hours=2),
                    venue_name="Park", town="Kisumu", county="Kisumu", is_free=True)
        data.update(kw)
        return Event.objects.create(**data)


class EventConstraintTests(Base):
    def test_end_must_be_after_start_in_database(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.make_event(end_datetime=self.start - timedelta(hours=1))

    def test_paid_event_needs_price_in_database(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.make_event(is_free=False, ticket_price=None)

    def test_negative_ticket_price_is_rejected(self):
        e = self.make_event(is_free=False, ticket_price=Decimal("25"))
        e.ticket_price = Decimal("-1")
        with self.assertRaises(ValidationError):
            e.full_clean()
        with self.assertRaises(IntegrityError), transaction.atomic():
            Event.objects.filter(pk=e.pk).update(ticket_price=Decimal("-1"))

    def test_full_clean_reports_friendly_errors(self):
        e = Event(title="x", summary="s", description="d", category=self.cat, owner=self.owner,
                  start_datetime=self.start, end_datetime=self.start - timedelta(hours=1), is_free=False, venue_name="V")
        with self.assertRaises(ValidationError) as cm:
            e.full_clean()
        self.assertIn("end_datetime", cm.exception.message_dict)
        self.assertIn("ticket_price", cm.exception.message_dict)

    def test_free_event_clears_price_on_clean(self):
        e = self.make_event()
        e.ticket_price = Decimal("500")
        e.full_clean()
        self.assertIsNone(e.ticket_price)

    def test_physical_event_needs_a_place_but_online_does_not(self):
        e = Event(title="x", summary="s", description="d", category=self.cat, owner=self.owner,
                  start_datetime=self.start, end_datetime=self.start + timedelta(hours=1))
        with self.assertRaises(ValidationError):
            e.full_clean()
        e.event_type = Event.EventType.ONLINE
        e.full_clean()

    def test_coordinates_must_come_as_a_pair_and_in_range(self):
        e = self.make_event()
        e.latitude = Decimal("-0.1")
        with self.assertRaises(ValidationError):
            e.full_clean()
        e.longitude = Decimal("34.75")
        e.full_clean()
        e.latitude = Decimal("123")
        with self.assertRaises(ValidationError):
            e.full_clean()


class EventBehaviourTests(Base):
    def test_defaults_to_pending(self):
        self.assertEqual(self.make_event().status, Event.Status.PENDING)

    def test_slugs_are_unique(self):
        a, b = self.make_event(), self.make_event()
        self.assertEqual(a.slug, "fun-run")
        self.assertEqual(b.slug, "fun-run-2")

    def test_published_manager_hides_everything_else(self):
        pending = self.make_event(title="P")
        live = self.make_event(title="L", status=Event.Status.PUBLISHED)
        for s in (Event.Status.DRAFT, Event.Status.REJECTED, Event.Status.CANCELLED, Event.Status.COMPLETED):
            self.make_event(title=f"S-{s}", status=s)
        self.assertEqual(list(Event.objects.published()), [live])
        self.assertNotIn(pending, Event.objects.published())

    def test_saved_event_unique_per_user(self):
        e = self.make_event(status=Event.Status.PUBLISHED)
        SavedEvent.objects.create(user=self.other, event=e)
        with self.assertRaises(IntegrityError), transaction.atomic():
            SavedEvent.objects.create(user=self.other, event=e)
        SavedEvent.objects.create(user=self.owner, event=e)  # a different user is fine

    def test_one_open_report_per_user_but_can_report_again_after_handled(self):
        e = self.make_event(status=Event.Status.PUBLISHED)
        r = EventReport.objects.create(reporter=self.other, event=e, reason="SCAM")
        with self.assertRaises(IntegrityError), transaction.atomic():
            EventReport.objects.create(reporter=self.other, event=e, reason="OTHER")
        r.status = EventReport.Status.RESOLVED
        r.save()
        EventReport.objects.create(reporter=self.other, event=e, reason="OTHER")

    def test_organizer_one_per_user_and_slug(self):
        o = OrganizerProfile.objects.create(owner=self.owner, name="Lake Events")
        self.assertEqual(o.slug, "lake-events")
        with self.assertRaises(IntegrityError), transaction.atomic():
            OrganizerProfile.objects.create(owner=self.owner, name="Second")

    def test_category_in_use_cannot_be_deleted(self):
        from django.db.models import ProtectedError
        self.make_event()
        with self.assertRaises(ProtectedError):
            self.cat.delete()


class PermissionTests(Base):
    def test_owner_can_edit_own_not_others(self):
        e = self.make_event()
        self.assertTrue(e.can_edit(self.owner))
        self.assertFalse(e.can_edit(self.other))

    def test_staff_can_edit_any(self):
        self.assertTrue(self.make_event().can_edit(self.staff))

    def test_anonymous_and_inactive_cannot_edit(self):
        from django.contrib.auth.models import AnonymousUser
        e = self.make_event()
        self.assertFalse(e.can_edit(AnonymousUser()))
        self.owner.is_active = False
        self.assertFalse(e.can_edit(self.owner))

    def test_owner_cannot_edit_completed(self):
        e = self.make_event(status=Event.Status.COMPLETED)
        self.assertFalse(e.can_edit(self.owner))
        self.assertTrue(e.can_edit(self.staff))

    def test_unpublished_visible_only_to_owner_and_staff(self):
        from django.contrib.auth.models import AnonymousUser
        e = self.make_event(status=Event.Status.PENDING)
        self.assertFalse(e.can_view(AnonymousUser()))
        self.assertFalse(e.can_view(self.other))
        self.assertTrue(e.can_view(self.owner))
        self.assertTrue(e.can_view(self.staff))

    def test_cancelled_page_is_public(self):
        from django.contrib.auth.models import AnonymousUser
        self.assertTrue(self.make_event(status=Event.Status.CANCELLED).can_view(AnonymousUser()))


class SeedCommandTests(TestCase):
    def test_seed_is_idempotent(self):
        from django.core.management import call_command
        call_command("seed_categories", verbosity=0)
        call_command("seed_categories", verbosity=0)
        self.assertEqual(Category.objects.count(), 14)
