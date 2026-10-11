"""Public event queries. Everything the public sees comes through `live()`:
published events that haven't ended. Other statuses are never discoverable."""
from datetime import datetime, time, timedelta

from django.db.models import Count, Q
from django.utils import timezone

from .constants import KENYA_COUNTIES
from .models import Category, Event

SORT_CHOICES = [("upcoming", "Soonest first"), ("recent", "Recently added")]
WHEN_CHOICES = [
    ("", "Any date"),
    ("today", "Today"),
    ("week", "This week"),
    ("weekend", "This weekend"),
    ("month", "This month"),
]
PRICE_CHOICES = [("", "Free and paid"), ("free", "Free only"), ("paid", "Paid only")]
MAX_TERMS = 8


def live():
    return Event.objects.published().upcoming().select_related("category", "organizer")


def _day_start(day):
    return timezone.make_aware(datetime.combine(day, time.min))


def _overlapping(qs, first_day, last_day):
    """Events that overlap the local-day range [first_day, last_day]."""
    return qs.filter(start_datetime__lt=_day_start(last_day + timedelta(days=1)), end_datetime__gte=_day_start(first_day))


def _range_for(when, today):
    if when == "today":
        return today, today
    if when == "week":
        return today, today + timedelta(days=6)
    if when == "weekend":
        if today.weekday() == 6:  # Sunday: the weekend is today
            return today, today
        saturday = today + timedelta(days=(5 - today.weekday()) % 7)
        return saturday, saturday + timedelta(days=1)
    if when == "month":
        return today, today + timedelta(days=30)
    return None


def search(q="", category="", location="", when="", on="", price="", sort="upcoming"):
    qs = live()

    for term in (q or "").split()[:MAX_TERMS]:  # every word must match somewhere
        qs = qs.filter(
            Q(title__icontains=term) | Q(summary__icontains=term) | Q(description__icontains=term)
            | Q(venue_name__icontains=term) | Q(town__icontains=term) | Q(county__icontains=term)
            | Q(organizer__name__icontains=term) | Q(category__name__icontains=term)
        )
    if category:
        qs = qs.filter(category__slug=category)
    location = (location or "").strip()
    if location:
        qs = qs.filter(Q(town__icontains=location) | Q(county__icontains=location) | Q(address__icontains=location))

    day_range = None
    if on:
        try:
            d = datetime.strptime(on, "%Y-%m-%d").date()
            day_range = (d, d)
        except ValueError:
            day_range = None  # ignore malformed dates instead of erroring
    if day_range is None:
        day_range = _range_for(when, timezone.localdate())
    if day_range:
        qs = _overlapping(qs, *day_range)

    if price == "free":
        qs = qs.filter(is_free=True)
    elif price == "paid":
        qs = qs.filter(is_free=False)

    if sort == "recent":
        return qs.order_by("-published_at", "-id")
    return qs.order_by("start_datetime", "id")


# ---- homepage sections ----------------------------------------------------
def featured(limit=3):
    return live().filter(is_featured=True).order_by("start_datetime")[:limit]


def trending(limit=4):
    """Upcoming events people have saved the most. Needs at least one save."""
    return live().annotate(saves=Count("saved_by")).filter(saves__gt=0).order_by("-saves", "start_datetime")[:limit]


def happening_today(limit=4):
    today = timezone.localdate()
    return _overlapping(live(), today, today).order_by("start_datetime")[:limit]


def coming_this_week(limit=4):
    today = timezone.localdate()
    return _overlapping(live(), today + timedelta(days=1), today + timedelta(days=6)).filter(
        start_datetime__gte=_day_start(today + timedelta(days=1))).order_by("start_datetime")[:limit]


def recently_added(limit=4):
    return live().order_by("-published_at", "-id")[:limit]


def related(event, limit=3):
    same = list(live().filter(category=event.category).exclude(pk=event.pk).order_by("start_datetime")[:limit])
    if len(same) < limit:
        have = [e.pk for e in same] + [event.pk]
        same += list(live().exclude(pk__in=have).order_by("start_datetime")[: limit - len(same)])
    return same


# ---- categories and locations --------------------------------------------
def categories_with_counts():
    live_q = Q(events__status=Event.Status.PUBLISHED, events__end_datetime__gte=timezone.now())
    return Category.objects.annotate(live_count=Count("events", filter=live_q)).order_by("name")


def popular_categories(limit=8):
    return categories_with_counts().order_by("-live_count", "name")[:limit]


def locations():
    towns = set(live().exclude(town="").order_by().values_list("town", flat=True).distinct())
    return sorted(set(KENYA_COUNTIES) | towns)
