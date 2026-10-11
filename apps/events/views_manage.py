"""Signed-in event management: dashboard, create, edit, status actions, organizer profile."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.accounts.ratelimit import rate_limit

from . import workflow
from .forms import EventForm, OrganizerProfileForm
from .models import Event, OrganizerProfile


def _own_event(request, pk):
    # 404 (not 403) for other people's events: don't reveal that they exist.
    return get_object_or_404(Event.objects.select_related("category"), pk=pk, owner=request.user)


@login_required
def my_events(request):
    base = Event.objects.filter(owner=request.user).select_related("category")
    counts = {row["status"]: row["n"] for row in base.values("status").annotate(n=Count("id"))}
    status = request.GET.get("status", "")
    events = base.filter(status=status) if status in Event.Status.values else base
    page = Paginator(events.order_by("-updated_at"), 20).get_page(request.GET.get("page"))
    tabs = [("", "All", sum(counts.values()))] + [(v, l, counts.get(v, 0)) for v, l in Event.Status.choices]
    return render(request, "dashboard/list.html", {
        "page": page, "tabs": tabs, "current": status if status in Event.Status.values else "",
        "has_organizer": OrganizerProfile.objects.filter(owner=request.user).exists(),
    })


def _save_event(request, form, event=None):
    """Shared save logic for create and edit. Returns the saved event."""
    submit = request.POST.get("action") == "submit"
    with transaction.atomic():
        saved = form.save(commit=False)
        if event is None:
            saved.owner = request.user
            saved.status = Event.Status.DRAFT
        saved.save()
        form.save_m2m()
        message = workflow.after_owner_edit(saved, changed=event is not None and form.has_changed(), submit=submit)
    form.delete_replaced_image(saved)  # only after the transaction committed
    messages.success(request, message)
    return saved


@login_required
@rate_limit("event-save", limit=30, window=3600)
def event_create(request):
    form = EventForm(request.POST or None, request.FILES or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        try:
            _save_event(request, form)
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            return redirect("dashboard:list")
    return render(request, "dashboard/event_form.html", {"form": form, "event": None})


@login_required
@rate_limit("event-save", limit=30, window=3600)
def event_edit(request, pk):
    event = _own_event(request, pk)
    if not event.can_edit(request.user):
        messages.error(request, f"{event.get_status_display()} events can't be edited.")
        return redirect("dashboard:list")
    form = EventForm(request.POST or None, request.FILES or None, instance=event, user=request.user)
    if request.method == "POST" and form.is_valid():
        try:
            _save_event(request, form, event)
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            return redirect("dashboard:list")
    return render(request, "dashboard/event_form.html", {"form": form, "event": event})


def _transition(request, pk, action, success):
    event = _own_event(request, pk)
    try:
        action(event)
    except workflow.InvalidTransition as exc:
        messages.error(request, str(exc))
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
    else:
        messages.success(request, success)
    return redirect("dashboard:list")


@login_required
@require_POST
@rate_limit("event-save", limit=30, window=3600)
def event_submit(request, pk):
    return _transition(request, pk, workflow.submit_for_review,
                       "Submitted for review. We'll email you when it's approved or if it needs changes.")


@login_required
@require_POST
def event_withdraw(request, pk):
    return _transition(request, pk, workflow.withdraw, "Withdrawn. The event is back in your drafts.")


@login_required
@require_POST
def event_cancel(request, pk):
    return _transition(request, pk, lambda e: workflow.cancel(e, request.user), "Event cancelled.")


@login_required
@require_POST
def event_delete(request, pk):
    event = _own_event(request, pk)
    if event.status not in {Event.Status.DRAFT, Event.Status.REJECTED}:
        messages.error(request, "Only drafts and rejected events can be deleted. Cancel a published event instead.")
        return redirect("dashboard:list")
    if event.cover_image:
        event.cover_image.delete(save=False)
    event.delete()
    messages.success(request, "Event deleted.")
    return redirect("dashboard:list")


@login_required
def organizer_edit(request):
    profile = OrganizerProfile.objects.filter(owner=request.user).first()
    form = OrganizerProfileForm(request.POST or None, request.FILES or None, instance=profile)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.owner = request.user
        obj.save()
        messages.success(request, "Organizer profile saved.")
        return redirect("dashboard:list")
    return render(request, "dashboard/organizer_form.html", {"form": form, "profile": profile})
