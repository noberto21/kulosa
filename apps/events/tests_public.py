import json
import re
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from . import services, workflow
from .admin import EventReportAdmin
from .models import Category, Event, EventReport, OrganizerProfile, SavedEvent

User = get_user_model()


def at(days=0, hour=18, hours=3):
    base = timezone.localtime().replace(hour=hour, minute=0, second=0, microsecond=0) + timedelta(days=days)
    return base, base + timedelta(hours=hours)


class Base(TestCase):
    def setUp(self):
        cache.clear()
        self.music = Category.objects.create(name="Music & Concerts", slug="music-concerts")
        self.sports = Category.objects.create(name="Sports", slug="sports")
        self.owner = User.objects.create_user("owner@example.com", "pw-Owner-1234", full_name="Owner One")
        self.fan = User.objects.create_user("fan@example.com", "pw-Fan-12345", full_name="Fan Two")
        self.staff = User.objects.create_superuser("staff@example.com", "pw-Staff-1234", full_name="Staff")

    def ev(self, title="Event", days=3, status="PUBLISHED", category=None, **kw):
        start, end = at(days)
        data = dict(title=title, summary=f"{title} summary", description=f"{title} description", category=category or self.music,
                    owner=self.owner, start_datetime=start, end_datetime=end, venue_name="Hall", address="Main St",
                    county="Kisumu", town="Kisumu", is_free=True, status=status)
        data.update(kw)
        return Event.objects.create(**data)

    def titles(self, **params):
        return [e.title for e in services.search(**params)]


class VisibilityTests(Base):
    def test_only_published_upcoming_events_are_discoverable(self):
        self.ev("Live")
        for s in ("DRAFT", "PENDING", "REJECTED", "CANCELLED", "COMPLETED"):
            self.ev(f"Hidden {s}", status=s)
        past_s, past_e = at(-3)
        self.ev("Ended", start_datetime=past_s, end_datetime=past_e)
        self.assertEqual(self.titles(), ["Live"])
        r = self.client.get(reverse("events:explore"))
        self.assertContains(r, "Live")
        self.assertNotContains(r, "Hidden")
        self.assertNotContains(r, ">Ended<")

    def test_homepage_never_leaks_unpublished(self):
        self.ev("Secret pending", status="PENDING", is_featured=True)
        r = self.client.get("/")
        self.assertNotContains(r, "Secret pending")
        self.assertContains(r, "No events are listed yet")

    def test_in_progress_event_still_listed(self):
        now = timezone.now()
        self.ev("Happening now", start_datetime=now - timedelta(hours=1), end_datetime=now + timedelta(hours=2))
        self.assertEqual(self.titles(), ["Happening now"])


class SearchTests(Base):
    def setUp(self):
        super().setUp()
        org = OrganizerProfile.objects.create(owner=self.owner, name="Lake Collective")
        self.run_ev = self.ev("Lakeside Fun Run", days=2, category=self.sports, town="Kisumu", county="Kisumu", organizer=org,
                              description="Bring water and good shoes.", is_free=True)
        self.gig = self.ev("Nairobi Jazz Night", days=5, category=self.music, town="Westlands", county="Nairobi",
                           is_free=False, ticket_price=1000, venue_name="Jazz Hall")
        self.fair = self.ev("Eldoret Career Fair", days=40, category=self.music, town="Eldoret", county="Uasin Gishu")

    def test_keyword_in_title_summary_description_venue_organizer_category(self):
        self.assertEqual(self.titles(q="jazz"), ["Nairobi Jazz Night"])
        self.assertEqual(self.titles(q="shoes"), ["Lakeside Fun Run"])
        self.assertEqual(self.titles(q="Jazz Hall"), ["Nairobi Jazz Night"])
        self.assertEqual(self.titles(q="collective"), ["Lakeside Fun Run"])
        self.assertEqual(set(self.titles(q="sports")), {"Lakeside Fun Run"})

    def test_all_words_must_match_and_case_is_ignored(self):
        self.assertEqual(self.titles(q="LAKESIDE run"), ["Lakeside Fun Run"])
        self.assertEqual(self.titles(q="lakeside jazz"), [])

    def test_special_characters_are_just_text(self):
        for q in ["%", "_", "' OR 1=1 --", "<script>", "\\", "a" * 500]:
            self.assertEqual(self.titles(q=q), [], q)

    def test_category_location_price(self):
        self.assertEqual(self.titles(category="sports"), ["Lakeside Fun Run"])
        self.assertEqual(self.titles(category="no-such"), [])
        self.assertEqual(self.titles(location="nairobi"), ["Nairobi Jazz Night"])
        self.assertEqual(self.titles(location="westlands"), ["Nairobi Jazz Night"])
        self.assertEqual(self.titles(location="Uasin"), ["Eldoret Career Fair"])
        self.assertEqual(set(self.titles(price="free")), {"Lakeside Fun Run", "Eldoret Career Fair"})
        self.assertEqual(self.titles(price="paid"), ["Nairobi Jazz Night"])

    def test_date_filters(self):
        today = timezone.localdate()
        self.assertEqual(self.titles(when="today"), [])
        self.assertEqual(set(self.titles(when="week")), {"Lakeside Fun Run", "Nairobi Jazz Night"})  # days=2 and 5
        self.assertNotIn("Eldoret Career Fair", self.titles(when="month"))
        on = (today + timedelta(days=40)).isoformat()
        self.assertEqual(self.titles(on=on), ["Eldoret Career Fair"])
        self.assertEqual(self.titles(on="not-a-date"), self.titles())  # malformed dates are ignored

    def test_event_today_and_overnight_events_match_day_filter(self):
        now = timezone.localtime()
        t0 = now - timedelta(minutes=10)
        self.ev("Today thing", start_datetime=t0, end_datetime=t0 + timedelta(hours=2))
        start = now.replace(hour=22, minute=0) + timedelta(days=1)
        self.ev("Overnight", start_datetime=start, end_datetime=start + timedelta(hours=8))
        d2 = (timezone.localdate() + timedelta(days=2)).isoformat()
        self.assertIn("Overnight", self.titles(on=d2))

    def test_sorting(self):
        self.assertEqual(self.titles(sort="upcoming")[0], "Lakeside Fun Run")
        newest = self.ev("Brand New Listing", days=60)
        self.assertEqual(self.titles(sort="recent")[0], "Brand New Listing")
        self.assertEqual(newest.title, "Brand New Listing")

    def test_explore_page_params_and_pagination(self):
        for i in range(12):
            self.ev(f"Bulk {i}", days=10 + i)
        r = self.client.get(reverse("events:explore") + "?q=bulk")
        self.assertContains(r, "12 events found")
        self.assertEqual(len(r.context["page"].object_list), 9)
        r2 = self.client.get(reverse("events:explore") + "?q=bulk&page=2")
        self.assertEqual(len(r2.context["page"].object_list), 3)
        self.assertContains(r2, "q=bulk&amp;page=1")
        self.assertEqual(self.client.get(reverse("events:explore") + "?page=abc").status_code, 200)
        self.assertEqual(self.client.get(reverse("events:explore") + "?page=999").status_code, 200)
        self.assertEqual(self.client.get(reverse("events:explore") + "?sort=evil&when=x&price=y").status_code, 200)

    def test_empty_results_state(self):
        r = self.client.get(reverse("events:explore") + "?q=zzzzzz")
        self.assertContains(r, "No events match those filters")

    def test_explore_query_count_is_bounded(self):
        for i in range(9):
            self.ev(f"Q{i}", days=20 + i)
        with self.assertNumQueries(4):  # count, categories, towns, page of events: constant, no N+1
            self.client.get(reverse("events:explore"))


class DateRangeTests(TestCase):
    def test_weekend_and_week_ranges_for_every_weekday(self):
        from datetime import date
        monday = date(2026, 10, 12)  # a Monday
        sat, sun = date(2026, 10, 17), date(2026, 10, 18)
        for offset in range(5):  # Mon..Fri -> the coming Saturday and Sunday
            self.assertEqual(services._range_for("weekend", monday + timedelta(days=offset)), (sat, sun))
        self.assertEqual(services._range_for("weekend", sat), (sat, sun))
        self.assertEqual(services._range_for("weekend", sun), (sun, sun))
        self.assertEqual(services._range_for("week", monday), (monday, date(2026, 10, 18)))
        self.assertEqual(services._range_for("today", monday), (monday, monday))
        self.assertIsNone(services._range_for("", monday))
        self.assertIsNone(services._range_for("bogus", monday))


class SectionTests(Base):
    def test_featured_only_published_and_flagged(self):
        self.ev("Featured one", is_featured=True)
        self.ev("Plain")
        self.ev("Featured but pending", status="PENDING", is_featured=True)
        self.assertEqual([e.title for e in services.featured()], ["Featured one"])

    def test_trending_needs_saves_and_orders_by_count(self):
        a, b, c = self.ev("A"), self.ev("B", days=4), self.ev("C", days=5)
        SavedEvent.objects.create(user=self.fan, event=b)
        SavedEvent.objects.create(user=self.owner, event=b)
        SavedEvent.objects.create(user=self.fan, event=c)
        self.assertEqual([e.title for e in services.trending()], ["B", "C"])

    def test_today_and_this_week_sections(self):
        now = timezone.localtime()
        today_ev = self.ev("Today", start_datetime=now - timedelta(minutes=30), end_datetime=now + timedelta(hours=3))
        tomorrow = self.ev("Tomorrow", days=1)
        later = self.ev("Next month", days=30)
        self.assertEqual([e.pk for e in services.happening_today()], [today_ev.pk])
        self.assertEqual([e.pk for e in services.coming_this_week()], [tomorrow.pk])
        self.assertNotIn(later.pk, [e.pk for e in services.coming_this_week()])

    def test_recently_added_orders_by_publish_time(self):
        old = self.ev("Old", days=3)
        new = self.ev("New", days=20)
        Event.objects.filter(pk=old.pk).update(published_at=timezone.now() - timedelta(days=9))
        self.assertEqual([e.title for e in services.recently_added()], ["New", "Old"])

    def test_published_at_set_once_on_first_publish(self):
        e = self.ev("Later", status="PENDING")
        self.assertIsNone(e.published_at)
        workflow.approve(e, self.staff)
        first = e.published_at
        self.assertIsNotNone(first)
        e.status = "PENDING"; e.save()
        workflow.approve(e, self.staff)
        self.assertEqual(e.published_at, first)

    def test_homepage_renders_sections(self):
        self.ev("Featured one", is_featured=True)
        r = self.client.get("/")
        self.assertContains(r, "Featured events")
        self.assertContains(r, "Recently added")
        self.assertNotContains(r, "No events are listed yet")

    def test_categories_page_counts_only_live_events(self):
        self.ev("L1"); self.ev("L2"); self.ev("Hidden", status="PENDING")
        r = self.client.get(reverse("core:categories"))
        self.assertContains(r, "2 upcoming events")
        self.assertContains(r, "0 upcoming events")  # Sports

    def test_category_filter_link_works(self):
        self.ev("Sport thing", category=self.sports)
        self.ev("Music thing")
        r = self.client.get(reverse("events:explore") + "?category=sports")
        self.assertContains(r, "Sport thing")
        self.assertNotContains(r, "Music thing")


class DetailTests(Base):
    def test_published_page_and_content(self):
        org = OrganizerProfile.objects.create(owner=self.owner, name="Lake Collective", contact_email="hi@lake.example")
        e = self.ev("Fun Run", is_free=False, ticket_price=300, booking_url="https://tickets.example.com/x", organizer=org)
        r = self.client.get(e.get_absolute_url())
        self.assertContains(r, "Fun Run")
        self.assertContains(r, "KES 300")
        self.assertContains(r, 'href="https://tickets.example.com/x"')
        self.assertContains(r, 'rel="noopener noreferrer nofollow"')
        self.assertContains(r, "Lake Collective")
        self.assertContains(r, "hi@lake.example")
        self.assertContains(r, "wa.me")
        self.assertContains(r, "data-copy-link")
        self.assertContains(r, 'property="og:title"')
        self.assertContains(r, 'rel="canonical"')
        self.assertNotContains(r, 'content="noindex')
        self.assertContains(r, "does not sell tickets")

    def test_unpublished_pages_are_404_for_the_public_but_preview_for_owner_and_staff(self):
        for status in ("DRAFT", "PENDING", "REJECTED"):
            e = self.ev(f"Hid {status}", status=status)
            self.assertEqual(self.client.get(e.get_absolute_url()).status_code, 404, status)
            self.client.force_login(self.fan)
            self.assertEqual(self.client.get(e.get_absolute_url()).status_code, 404, status)
            self.client.force_login(self.owner)
            r = self.client.get(e.get_absolute_url())
            self.assertContains(r, "Preview.")
            self.assertContains(r, 'content="noindex')
            self.client.force_login(self.staff)
            self.assertEqual(self.client.get(e.get_absolute_url()).status_code, 200)
            self.client.logout()

    def test_cancelled_event_shows_notice_and_no_ticket_button(self):
        e = self.ev("Called off", status="CANCELLED", booking_url="https://tickets.example.com/x", is_free=False, ticket_price=100)
        r = self.client.get(e.get_absolute_url())
        self.assertContains(r, "This event has been cancelled")
        self.assertNotContains(r, "Get tickets")
        self.assertNotContains(r, "Save event")
        self.assertContains(r, 'content="noindex')
        self.assertIn("EventCancelled", r.content.decode())

    def test_completed_event_is_viewable_but_not_listed(self):
        e = self.ev("Over", status="COMPLETED", booking_url="https://tickets.example.com/x")
        r = self.client.get(e.get_absolute_url())
        self.assertContains(r, "This event has ended")
        self.assertNotContains(r, "Get tickets")
        self.assertEqual(self.titles(), [])

    def test_ended_but_not_yet_marked_completed_shows_ended(self):
        s, en = at(-3)
        e = self.ev("Just ended", start_datetime=s, end_datetime=en, booking_url="https://tickets.example.com/x")
        r = self.client.get(e.get_absolute_url())
        self.assertContains(r, "This event has ended")
        self.assertNotContains(r, "Get tickets")

    def test_unknown_slug_404(self):
        self.assertEqual(self.client.get("/events/nope/").status_code, 404)

    def test_user_content_is_escaped(self):
        e = self.ev("<img src=x onerror=alert(1)>", description="<script>alert('d')</script>\nline two",
                    venue_name="<b>Hall</b>")
        r = self.client.get(e.get_absolute_url())
        body = r.content.decode()
        self.assertNotIn("<script>alert('d')</script>", body)
        self.assertNotIn("<img src=x onerror", body)
        self.assertNotIn("<b>Hall</b>", body)
        self.assertIn("&lt;script&gt;", body)

    def test_jsonld_is_valid_and_cannot_break_out_of_script_tag(self):
        e = self.ev("Evil </script><script>alert(1)</script>", summary="x </script> y")
        body = self.client.get(e.get_absolute_url()).content.decode()
        m = re.search(r'<script type="application/ld\+json">(.*?)</script>', body, re.S)
        data = json.loads(m.group(1))
        self.assertEqual(data["@type"], "Event")
        self.assertEqual(data["name"], "Evil </script><script>alert(1)</script>")
        self.assertEqual(data["eventStatus"], "https://schema.org/EventScheduled")
        self.assertEqual(data["location"]["address"]["addressCountry"], "KE")
        self.assertNotIn("</script><script>alert(1)", body)

    def test_online_event_jsonld_and_display(self):
        e = self.ev("Webinar", event_type="ONLINE", venue_name="", address="", town="", county="", booking_url="https://meet.example.com/x")
        r = self.client.get(e.get_absolute_url())
        self.assertContains(r, "Online event")
        self.assertIn("OnlineEventAttendanceMode", r.content.decode())

    def test_related_events_prefer_same_category(self):
        main = self.ev("Main", category=self.sports)
        same = self.ev("Same cat", category=self.sports, days=4)
        other = self.ev("Other cat", category=self.music, days=5)
        self.ev("Hidden", category=self.sports, status="PENDING")
        rel = [e.title for e in services.related(main)]
        self.assertEqual(rel[0], "Same cat")
        self.assertIn("Other cat", rel)
        self.assertNotIn("Main", rel)
        self.assertNotIn("Hidden", rel)

    def test_slug_is_stable_when_title_changes(self):
        e = self.ev("Original name")
        slug = e.slug
        e.title = "Renamed"
        e.save()
        self.assertEqual(Event.objects.get(pk=e.pk).slug, slug)


class FavoritesTests(Base):
    def test_anonymous_cannot_save_and_sees_login_prompt(self):
        e = self.ev("Fav")
        r = self.client.post(reverse("events:save", args=[e.slug]))
        self.assertIn("/login/", r["Location"])
        self.assertEqual(SavedEvent.objects.count(), 0)
        self.assertContains(self.client.get(e.get_absolute_url()), "Log in to save this event")

    def test_save_and_unsave_are_idempotent(self):
        e = self.ev("Fav")
        self.client.force_login(self.fan)
        for _ in range(2):
            self.client.post(reverse("events:save", args=[e.slug]))
        self.assertEqual(SavedEvent.objects.filter(user=self.fan, event=e).count(), 1)
        self.assertContains(self.client.get(e.get_absolute_url()), "Saved. Click to remove")
        for _ in range(2):
            self.client.post(reverse("events:unsave", args=[e.slug]))
        self.assertEqual(SavedEvent.objects.count(), 0)

    def test_get_is_rejected_and_csrf_enforced(self):
        from django.test import Client
        e = self.ev("Fav")
        self.client.force_login(self.fan)
        self.assertEqual(self.client.get(reverse("events:save", args=[e.slug])).status_code, 405)
        c = Client(enforce_csrf_checks=True); c.force_login(self.fan)
        self.assertEqual(c.post(reverse("events:save", args=[e.slug])).status_code, 403)

    def test_cannot_save_unpublished_event(self):
        e = self.ev("Pending", status="PENDING")
        self.client.force_login(self.fan)
        self.assertEqual(self.client.post(reverse("events:save", args=[e.slug])).status_code, 404)

    def test_next_redirect_is_safe(self):
        e = self.ev("Fav")
        self.client.force_login(self.fan)
        r = self.client.post(reverse("events:save", args=[e.slug]), {"next": "https://evil.example/x"})
        self.assertEqual(r["Location"], e.get_absolute_url())
        r = self.client.post(reverse("events:save", args=[e.slug]), {"next": "/saved/"})
        self.assertEqual(r["Location"], "/saved/")

    def test_saved_page_is_private_and_lists_only_public_events(self):
        mine, cancelled, theirs = self.ev("Mine"), self.ev("Cancelled one", status="CANCELLED"), self.ev("Theirs")
        pending = self.ev("Went pending", status="PENDING")
        SavedEvent.objects.create(user=self.fan, event=mine)
        SavedEvent.objects.create(user=self.fan, event=cancelled)
        SavedEvent.objects.create(user=self.fan, event=pending)
        SavedEvent.objects.create(user=self.owner, event=theirs)
        self.assertIn("/login/", self.client.get(reverse("saved_events"))["Location"])
        self.client.force_login(self.fan)
        r = self.client.get(reverse("saved_events"))
        self.assertContains(r, "Mine")
        self.assertContains(r, "Cancelled one")
        self.assertContains(r, ">Cancelled<")
        self.assertNotContains(r, "Went pending")
        self.assertNotContains(r, "Theirs")

    def test_user_cannot_unsave_someone_elses_save(self):
        e = self.ev("Fav")
        SavedEvent.objects.create(user=self.owner, event=e)
        self.client.force_login(self.fan)
        self.client.post(reverse("events:unsave", args=[e.slug]))
        self.assertEqual(SavedEvent.objects.filter(user=self.owner).count(), 1)


class ReportTests(Base):
    def test_login_required(self):
        e = self.ev("Shady")
        self.assertIn("/login/", self.client.get(reverse("events:report", args=[e.slug]))["Location"])

    def test_report_created_and_duplicate_blocked(self):
        e = self.ev("Shady")
        self.client.force_login(self.fan)
        url = reverse("events:report", args=[e.slug])
        self.assertEqual(self.client.get(url).status_code, 200)
        r = self.client.post(url, {"reason": "SCAM", "description": "Asks for M-Pesa upfront"}, follow=True)
        self.assertContains(r, "Thanks. Our team will review")
        self.assertEqual(EventReport.objects.filter(event=e, reporter=self.fan, status="OPEN").count(), 1)
        r = self.client.post(url, {"reason": "OTHER", "description": "again"}, follow=True)
        self.assertContains(r, "already reported")
        self.assertEqual(EventReport.objects.count(), 1)

    def test_other_reason_needs_description_and_reason_required(self):
        e = self.ev("Shady")
        self.client.force_login(self.fan)
        url = reverse("events:report", args=[e.slug])
        self.assertContains(self.client.post(url, {"reason": "OTHER", "description": "  "}), "Please describe the problem")
        self.assertContains(self.client.post(url, {"reason": "", "description": "x"}), "This field is required")
        self.assertEqual(EventReport.objects.count(), 0)

    def test_cannot_report_own_or_unpublished_event(self):
        own = self.ev("Own")
        self.client.force_login(self.owner)
        r = self.client.post(reverse("events:report", args=[own.slug]), {"reason": "SCAM"}, follow=True)
        self.assertEqual(EventReport.objects.count(), 0)
        pending = self.ev("P", status="PENDING")
        self.client.force_login(self.fan)
        self.assertEqual(self.client.get(reverse("events:report", args=[pending.slug])).status_code, 404)

    def test_can_report_again_after_previous_report_handled(self):
        e = self.ev("Shady")
        EventReport.objects.create(reporter=self.fan, event=e, reason="SCAM", status="RESOLVED")
        self.client.force_login(self.fan)
        self.client.post(reverse("events:report", args=[e.slug]), {"reason": "SCAM", "description": "back again"})
        self.assertEqual(EventReport.objects.filter(status="OPEN").count(), 1)

    def test_report_rate_limited(self):
        self.client.force_login(self.fan)
        events = [self.ev(f"E{i}", days=3 + i) for i in range(11)]
        codes = [self.client.post(reverse("events:report", args=[e.slug]), {"reason": "SCAM"}).status_code for e in events]
        self.assertEqual(codes[:10], [302] * 10)
        self.assertEqual(codes[10], 429)

    @override_settings(MODERATOR_EMAILS=["mod@example.com"])
    def test_moderators_emailed_about_reports_and_submissions(self):
        e = self.ev("Shady")
        self.client.force_login(self.fan)
        self.client.post(reverse("events:report", args=[e.slug]), {"reason": "SCAM", "description": "bad"})
        self.assertEqual(mail.outbox[-1].to, ["mod@example.com"])
        self.assertIn("Event reported", mail.outbox[-1].subject)
        draft = self.ev("New one", status="DRAFT")
        workflow.submit_for_review(draft)
        self.assertIn("Review needed", mail.outbox[-1].subject)

    def test_no_moderator_email_when_unconfigured(self):
        draft = self.ev("New one", status="DRAFT")
        workflow.submit_for_review(draft)
        self.assertEqual(len(mail.outbox), 0)


class AdminTests(Base):
    def test_report_actions_set_handler(self):
        e = self.ev("Shady")
        r1 = EventReport.objects.create(reporter=self.fan, event=e, reason="SCAM")
        self.client.force_login(self.staff)
        self.client.post(reverse("admin:events_eventreport_changelist"), {"action": "mark_resolved", "_selected_action": [r1.pk]})
        r1.refresh_from_db()
        self.assertEqual((r1.status, r1.handled_by), ("RESOLVED", self.staff))
        self.assertIsNotNone(r1.handled_at)

    def test_event_changelist_shows_open_report_count_and_feature_actions(self):
        e = self.ev("Shady")
        EventReport.objects.create(reporter=self.fan, event=e, reason="SCAM")
        self.client.force_login(self.staff)
        r = self.client.get(reverse("admin:events_event_changelist"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Open reports")
        self.client.post(reverse("admin:events_event_changelist"), {"action": "feature_selected", "_selected_action": [e.pk]})
        e.refresh_from_db()
        self.assertTrue(e.is_featured)
        pending = self.ev("Pend", status="PENDING")
        self.client.post(reverse("admin:events_event_changelist"), {"action": "feature_selected", "_selected_action": [pending.pk]})
        pending.refresh_from_db()
        self.assertFalse(pending.is_featured)


class OrganizerPageTests(Base):
    def test_lists_only_live_events(self):
        org = OrganizerProfile.objects.create(owner=self.owner, name="Lake Collective", is_verified=True)
        self.ev("Visible", organizer=org)
        self.ev("Not yet", organizer=org, status="PENDING")
        r = self.client.get(reverse("organizer_public", args=[org.slug]))
        self.assertContains(r, "Visible")
        self.assertContains(r, "Verified")
        self.assertNotContains(r, "Not yet")
        self.assertEqual(self.client.get("/organizers/nope/").status_code, 404)


class SeoTests(Base):
    def test_sitemap_lists_only_live_events(self):
        live, hidden = self.ev("Live one"), self.ev("Hidden one", status="PENDING")
        r = self.client.get("/sitemap.xml")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, live.slug)
        self.assertNotContains(r, hidden.slug)
        self.assertContains(r, "/events/")

    def test_robots_txt(self):
        r = self.client.get("/robots.txt")
        self.assertEqual(r["Content-Type"], "text/plain")
        body = r.content.decode()
        self.assertIn("Disallow: /admin/", body)
        self.assertIn("Disallow: /my-events/", body)
        self.assertIn("Sitemap: http://testserver/sitemap.xml", body)


class SeedDemoTests(TestCase):
    def test_create_refresh_and_remove(self):
        with override_settings(DEBUG=True):
            call_command("seed_demo_events", verbosity=0)
            n = Event.objects.count()
            self.assertGreater(n, 5)
            self.assertTrue(all(e.title.startswith("[Demo]") for e in Event.objects.all()))
            self.assertTrue(all(e.status == "PUBLISHED" for e in Event.objects.all()))
            call_command("seed_demo_events", verbosity=0)
            self.assertEqual(Event.objects.count(), n)
            call_command("seed_demo_events", "--remove", verbosity=0)
        self.assertEqual(Event.objects.count(), 0)
        self.assertFalse(User.objects.filter(email="demo-organizer@example.invalid").exists())

    def test_refuses_when_debug_off(self):
        with override_settings(DEBUG=False):
            with self.assertRaises(CommandError):
                call_command("seed_demo_events", verbosity=0)
        self.assertEqual(Event.objects.count(), 0)
