"""Event lifecycle rules in one place.

DRAFT --submit--> PENDING --approve--> PUBLISHED --cancel--> CANCELLED
                     |  \\--reject--> REJECTED --edit+submit--> PENDING
                     \\--withdraw--> DRAFT
PUBLISHED --(past end date)--> COMPLETED
A published event edited by its owner goes back to PENDING (re-moderation).
"""
from django.core.exceptions import ValidationError
from django.utils import timezone

from . import notifications
from .models import Event

S = Event.Status


class InvalidTransition(Exception):
    pass


def _require(event, allowed, verb):
    if event.status not in allowed:
        raise InvalidTransition(f"A {event.get_status_display().lower()} event can't be {verb}.")


def submit_for_review(event):
    _require(event, {S.DRAFT, S.REJECTED}, "submitted for review")
    event.full_clean()
    if event.end_datetime <= timezone.now():
        raise ValidationError("This event has already ended. Change its dates before submitting.")
    event.status = S.PENDING
    event.submitted_at = timezone.now()
    event.moderation_note = ""
    event.reviewed_by = None
    event.reviewed_at = None
    event.save()
    notifications.notify_new_submission(event)
    return event


def withdraw(event):
    _require(event, {S.PENDING}, "withdrawn")
    event.status = S.DRAFT
    event.save(update_fields=["status", "updated_at"])
    return event


def _record_review(event, moderator, status):
    event.status = status
    event.reviewed_by = moderator
    event.reviewed_at = timezone.now()


def approve(event, moderator):
    _require(event, {S.PENDING}, "approved")
    _record_review(event, moderator, S.PUBLISHED)
    event.moderation_note = ""
    event.save()
    return event


def reject(event, moderator, note):
    _require(event, {S.PENDING}, "rejected")
    note = (note or "").strip()
    if not note:
        raise ValidationError("Explain why the event was rejected so the organizer can fix it.")
    _record_review(event, moderator, S.REJECTED)
    event.moderation_note = note
    event.save()
    return event


def cancel(event, actor):
    _require(event, {S.PUBLISHED}, "cancelled")
    event.status = S.CANCELLED
    event.reviewed_by = actor if actor.is_staff else event.reviewed_by
    event.save()
    return event


def complete(event):
    _require(event, {S.PUBLISHED}, "completed")
    event.status = S.COMPLETED
    event.save(update_fields=["status", "updated_at"])
    return event


def after_owner_edit(event, changed, submit=False):
    """Apply status rules after an owner saves the edit form.
    Returns a short message describing what happened to the status."""
    if event.status == S.PUBLISHED and changed:
        event.status = S.PENDING
        event.submitted_at = timezone.now()
        event.reviewed_by = None
        event.reviewed_at = None
        event.save(update_fields=["status", "submitted_at", "reviewed_by", "reviewed_at", "updated_at"])
        notifications.notify_new_submission(event)
        return "Your changes were saved and sent for review. The event stays hidden until it's approved again."
    if submit and event.status in {S.DRAFT, S.REJECTED}:
        submit_for_review(event)
        return "Submitted for review. We'll email you when it's approved or if it needs changes."
    if event.status == S.PENDING:
        return "Changes saved. The event is still waiting for review."
    return "Draft saved." if event.status == S.DRAFT else "Changes saved."
