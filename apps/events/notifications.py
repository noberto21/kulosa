import logging

from django.conf import settings
from django.core.mail import send_mail
from django.urls import reverse

from .models import Event

log = logging.getLogger(__name__)


def send_review_result(event):
    """Email the owner when their event is approved or rejected. Never raises:
    a mail outage must not block moderation."""
    dashboard = settings.SITE_URL.rstrip("/") + reverse("dashboard:list")
    name = event.owner.get_short_name()
    if event.status == Event.Status.PUBLISHED:
        subject = f"Approved: {event.title}"
        body = f"Hi {name},\n\nYour event \"{event.title}\" has been approved.\n\nManage it here: {dashboard}\n\nKULOSA"
    elif event.status == Event.Status.REJECTED:
        subject = f"Changes needed: {event.title}"
        body = (f"Hi {name},\n\nYour event \"{event.title}\" wasn't approved yet.\n\n"
                f"Reason from the reviewer:\n{event.moderation_note}\n\n"
                f"Edit it and submit again here: {dashboard}\n\nKULOSA")
    else:
        return False
    try:
        send_mail(subject, body, None, [event.owner.email])
        return True
    except Exception:
        log.exception("Could not send review email for event %s", event.pk)
        return False


def notify_moderators(subject, body):
    """Email MODERATOR_EMAILS (if configured). Never raises."""
    recipients = settings.MODERATOR_EMAILS
    if not recipients:
        return False
    try:
        send_mail(subject, body, None, recipients)
        return True
    except Exception:
        log.exception("Could not send moderator email: %s", subject)
        return False


def _admin_url(name, pk):
    return settings.SITE_URL.rstrip("/") + reverse(name, args=[pk])


def notify_new_submission(event):
    return notify_moderators(
        f"Review needed: {event.title}",
        f"{event.owner.email} submitted \"{event.title}\" for review.\n\nOpen it: {_admin_url('admin:events_event_change', event.pk)}\n",
    )


def notify_new_report(report):
    return notify_moderators(
        f"Event reported: {report.event.title}",
        f"{report.reporter.email} reported \"{report.event.title}\" ({report.get_reason_display()}).\n\n"
        f"{report.description}\n\nOpen it: {_admin_url('admin:events_eventreport_change', report.pk)}\n",
    )
