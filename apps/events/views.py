from datetime import timezone as dt_timezone
from urllib.parse import quote

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from apps.accounts.ratelimit import rate_limit

from . import notifications, services
from .forms import ReportForm
from .models import Event, EventReport, OrganizerProfile, SavedEvent
from .seo import event_jsonld


def explore(request):
    params = {
        "q": request.GET.get("q", "").strip()[:100],
        "category": request.GET.get("category", ""),
        "location": request.GET.get("location", "").strip()[:60],
        "when": request.GET.get("when", ""),
        "on": request.GET.get("on", ""),
        "price": request.GET.get("price", ""),
        "sort": request.GET.get("sort", "upcoming"),
    }
    if params["sort"] not in dict(services.SORT_CHOICES):
        params["sort"] = "upcoming"

    paginator = Paginator(services.search(**params), 9)
    page = paginator.get_page(request.GET.get("page"))

    # Keep filters when moving between pages.
    keep = "&".join(f"{k}={quote(v)}" for k, v in params.items() if v and not (k == "sort" and v == "upcoming"))
    categories = list(services.categories_with_counts())
    return render(request, "events/explore.html", {
        "page": page,
        "total": paginator.count,
        "params": params,
        "querystring": keep,
        "has_filters": any(v for k, v in params.items() if k != "sort"),
        "selected_category": next((c for c in categories if c.slug == params["category"]), None),
        "categories": categories,
        "locations": services.locations(),
        "sort_choices": services.SORT_CHOICES,
        "when_choices": services.WHEN_CHOICES,
        "price_choices": services.PRICE_CHOICES,
        "site_has_events": paginator.count > 0 or services.live().exists(),
    })


def detail(request, slug):
    event = get_object_or_404(Event.objects.select_related("category", "organizer", "owner"), slug=slug)
    if not event.can_view(request.user):
        raise Http404("Event not found")  # unpublished events don't reveal themselves

    url = request.build_absolute_uri(event.get_absolute_url())
    text = quote(f"{event.title} on KULOSA")
    image_url = request.build_absolute_uri(event.poster_url) if event.poster_url else ""
    share = {
        "url": url,
        "whatsapp": f"https://wa.me/?text={text}%20{quote(url, safe='')}",
        "facebook": f"https://www.facebook.com/sharer/sharer.php?u={quote(url, safe='')}",
        "x": f"https://twitter.com/intent/tweet?text={text}&url={quote(url, safe='')}",
    }
    is_published = event.status == Event.Status.PUBLISHED

    start_utc = event.start_datetime.astimezone(dt_timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    end_utc = event.end_datetime.astimezone(dt_timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    loc_parts = [p for p in [event.venue_name, event.address, event.town, event.county] if p]
    loc_str = ", ".join(loc_parts) if event.event_type != Event.EventType.ONLINE else "Online"
    calendar_url = (
        f"https://calendar.google.com/calendar/render?action=TEMPLATE"
        f"&text={quote(event.title)}"
        f"&dates={start_utc}/{end_utc}"
        f"&details={quote(event.summary or event.title)}"
        f"&location={quote(loc_str)}"
    )

    maps_url = ""
    if event.event_type != Event.EventType.ONLINE:
        if event.latitude is not None and event.longitude is not None:
            maps_url = f"https://www.google.com/maps/search/?api=1&query={event.latitude},{event.longitude}"
        elif loc_str:
            maps_url = f"https://www.google.com/maps/search/?api=1&query={quote(loc_str + ', Kenya')}"

    return render(request, "events/detail.html", {
        "event": event,
        "share": share,
        "calendar_url": calendar_url,
        "maps_url": maps_url,
        "image_url": image_url,
        "canonical": url,
        "jsonld": event_jsonld(event, url, image_url) if event.is_public else "",
        "is_preview": not event.is_public,
        "can_save": is_published and not event.has_ended,
        "is_saved": request.user.is_authenticated and SavedEvent.objects.filter(user=request.user, event=event).exists(),
        "can_report": is_published and request.user.is_authenticated and event.owner_id != request.user.pk,
        "related": services.related(event) if is_published else [],
        "noindex": not is_published,
    })


def _safe_back(request, fallback):
    target = request.POST.get("next", "")
    if target and url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return target
    return fallback


@login_required
@require_POST
@rate_limit("favorite", limit=120, window=3600)
def save_event(request, slug):
    event = get_object_or_404(Event.objects.published(), slug=slug)
    _, created = SavedEvent.objects.get_or_create(user=request.user, event=event)
    messages.success(request, "Saved to your list." if created else "Already in your saved events.")
    return redirect(_safe_back(request, event.get_absolute_url()))


@login_required
@require_POST
@rate_limit("favorite", limit=120, window=3600)
def unsave_event(request, slug):
    SavedEvent.objects.filter(user=request.user, event__slug=slug).delete()
    messages.success(request, "Removed from your saved events.")
    return redirect(_safe_back(request, reverse("saved_events")))


@login_required
def saved_events(request):
    saved = (SavedEvent.objects.filter(user=request.user, event__status__in=Event.PUBLIC_STATUSES)
             .select_related("event__category").order_by("-created_at"))
    page = Paginator(saved, 12).get_page(request.GET.get("page"))
    return render(request, "events/saved.html", {"page": page, "events": [s.event for s in page.object_list]})


@login_required
@rate_limit("report", limit=10, window=3600)
def report_event(request, slug):
    event = get_object_or_404(Event.objects.published(), slug=slug)
    back = event.get_absolute_url()
    if event.owner_id == request.user.pk:
        messages.info(request, "This is your own event. Edit or cancel it from My events.")
        return redirect(back)
    if EventReport.objects.filter(reporter=request.user, event=event, status=EventReport.Status.OPEN).exists():
        messages.info(request, "You've already reported this event. Our team is reviewing it.")
        return redirect(back)

    form = ReportForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        report = form.save(commit=False)
        report.reporter, report.event = request.user, event
        try:
            with transaction.atomic():
                report.save()
        except IntegrityError:  # double-submit race: the open-report constraint caught it
            messages.info(request, "You've already reported this event. Our team is reviewing it.")
            return redirect(back)
        notifications.notify_new_report(report)
        messages.success(request, "Thanks. Our team will review this listing.")
        return redirect(back)
    return render(request, "events/report.html", {"form": form, "event": event})


def organizer_public(request, slug):
    organizer = get_object_or_404(OrganizerProfile, slug=slug)
    events = services.live().filter(organizer=organizer).order_by("start_datetime")
    page = Paginator(events, 9).get_page(request.GET.get("page"))
    return render(request, "events/organizer.html", {"organizer": organizer, "page": page})
