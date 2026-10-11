from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.events import workflow
from apps.events.models import Event


class Command(BaseCommand):
    help = "Mark published events whose end time has passed as COMPLETED. Run daily (cron / scheduler)."

    def handle(self, *args, **options):
        qs = Event.objects.published().filter(end_datetime__lt=timezone.now())
        n = 0
        for event in qs:
            workflow.complete(event)
            n += 1
        self.stdout.write(self.style.SUCCESS(f"{n} event(s) marked completed."))
