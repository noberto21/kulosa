import os
from decimal import Decimal
from uuid import uuid4

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.text import slugify


_ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp"}


def _random_upload_path(folder, filename):
    # Never keep user-supplied names: they can be hostile or leak personal info.
    ext = os.path.splitext(filename)[1].lower()
    ext = ext if ext in _ALLOWED_EXT else ".jpg"
    return f"{folder}/{uuid4().hex}{ext}"


def poster_upload_path(instance, filename):
    return _random_upload_path("events/posters", filename)


def logo_upload_path(instance, filename):
    return _random_upload_path("organizers/logos", filename)


def _unique_slug(model, base, instance_pk=None, max_length=200):
    """Return a slug unique within `model`, appending -2, -3... when needed."""
    base = (slugify(base) or "item")[: max_length - 8]
    slug, n = base, 2
    qs = model.objects.all()
    if instance_pk:
        qs = qs.exclude(pk=instance_pk)
    while qs.filter(slug=slug).exists():
        slug = f"{base}-{n}"
        n += 1
    return slug


class Category(models.Model):
    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=90, unique=True)
    description = models.CharField(max_length=200, blank=True)

    class Meta:
        verbose_name_plural = "categories"
        ordering = ["name"]

    def __str__(self):
        return self.name

    # Maps a category to its CSS poster placeholder (see static/css/input.css).
    POSTER_STYLES = {
        "music-concerts": "music", "sports": "sports", "festivals-carnivals": "festival",
        "parties-nightlife": "party", "technology-innovation": "tech", "education-campus": "campus",
        "business-networking": "business", "arts-culture": "arts", "food-drink": "food",
        "community-charity": "community", "travel-outdoor": "outdoor", "religious-events": "religious",
        "conferences-workshops": "conference",
    }

    @property
    def poster_style(self):
        return self.POSTER_STYLES.get(self.slug, "other")


class OrganizerProfile(models.Model):
    owner = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="organizer_profile")
    name = models.CharField("organization name", max_length=120)
    slug = models.SlugField(max_length=140, unique=True, blank=True)
    logo = models.ImageField(upload_to=logo_upload_path, blank=True)
    description = models.TextField(blank=True, max_length=2000)
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=20, blank=True)
    website = models.URLField(blank=True)
    is_verified = models.BooleanField(default=False, help_text="Set by an administrator after checking the organizer.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = _unique_slug(OrganizerProfile, self.name, self.pk, 140)
        super().save(*args, **kwargs)


class EventQuerySet(models.QuerySet):
    def published(self):
        """The only events the public may see."""
        return self.filter(status=Event.Status.PUBLISHED)

    def upcoming(self):
        return self.filter(end_datetime__gte=timezone.now())


class Event(models.Model):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        PENDING = "PENDING", "Pending review"
        PUBLISHED = "PUBLISHED", "Published"
        REJECTED = "REJECTED", "Rejected"
        CANCELLED = "CANCELLED", "Cancelled"
        COMPLETED = "COMPLETED", "Completed"

    class EventType(models.TextChoices):
        PHYSICAL = "PHYSICAL", "In person"
        ONLINE = "ONLINE", "Online"
        HYBRID = "HYBRID", "In person and online"

    title = models.CharField(max_length=160)
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    summary = models.CharField(max_length=240)
    description = models.TextField(max_length=8000)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="events")
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="events")
    organizer = models.ForeignKey(OrganizerProfile, null=True, blank=True, on_delete=models.SET_NULL, related_name="events")
    cover_image = models.ImageField(upload_to=poster_upload_path, blank=True)

    start_datetime = models.DateTimeField()
    end_datetime = models.DateTimeField()
    timezone = models.CharField(max_length=64, default="Africa/Nairobi")
    event_type = models.CharField(max_length=10, choices=EventType.choices, default=EventType.PHYSICAL)

    venue_name = models.CharField(max_length=160, blank=True)
    address = models.CharField(max_length=255, blank=True)
    county = models.CharField(max_length=60, blank=True)
    town = models.CharField(max_length=80, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True,
                                   validators=[MinValueValidator(Decimal("-90")), MaxValueValidator(Decimal("90"))])
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True,
                                    validators=[MinValueValidator(Decimal("-180")), MaxValueValidator(Decimal("180"))])

    is_free = models.BooleanField(default=True)
    ticket_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
                                       validators=[MinValueValidator(Decimal("0"))])
    currency = models.CharField(max_length=3, default="KES")
    booking_url = models.URLField(blank=True, max_length=500)

    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True)
    is_featured = models.BooleanField(default=False)
    submitted_at = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True, help_text="When the event was first approved. Drives 'recently added'.")
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="reviewed_events")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    moderation_note = models.TextField(blank=True, help_text="Shown to the submitter when an event is rejected.")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = EventQuerySet.as_manager()

    class Meta:
        ordering = ["start_datetime"]
        indexes = [
            models.Index(fields=["status", "start_datetime"]),
            models.Index(fields=["county", "town"]),
        ]
        constraints = [
            models.CheckConstraint(condition=Q(end_datetime__gt=models.F("start_datetime")), name="event_end_after_start"),
            models.CheckConstraint(
                condition=(Q(is_free=True) & Q(ticket_price__isnull=True))
                | (Q(is_free=False) & Q(ticket_price__isnull=False) & Q(ticket_price__gte=Decimal("0"))),
                name="event_paid_price_rules",
            ),
        ]

    def __str__(self):
        return self.title

    def clean(self):
        errors = {}
        if self.start_datetime and self.end_datetime and self.end_datetime <= self.start_datetime:
            errors["end_datetime"] = "The end time must be after the start time."
        if self.ticket_price is not None and self.ticket_price < 0:
            errors["ticket_price"] = "Ticket price cannot be negative."
        if not self.is_free and self.ticket_price is None:
            errors["ticket_price"] = "Enter a ticket price, or mark the event as free."
        if self.is_free:
            self.ticket_price = None
        if self.event_type != self.EventType.ONLINE and not (self.venue_name or self.address):
            errors["venue_name"] = "In-person and hybrid events need a venue or address."
        if (self.latitude is None) != (self.longitude is None):
            errors["latitude"] = "Provide both latitude and longitude, or neither."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = _unique_slug(Event, self.title, self.pk)
        if self.status == self.Status.PUBLISHED and self.published_at is None:
            self.published_at = timezone.now()
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse("events:detail", args=[self.slug])

    @property
    def has_ended(self):
        return self.end_datetime < timezone.now()

    @property
    def is_cancelled(self):
        return self.status == self.Status.CANCELLED

    # ---- permissions -------------------------------------------------
    @property
    def is_public(self):
        return self.status in {self.Status.PUBLISHED, self.Status.CANCELLED, self.Status.COMPLETED}

    def can_view(self, user):
        """Published/cancelled/completed pages are public; others only to owner and staff."""
        if self.is_public:
            return True
        return bool(user and user.is_authenticated and (user.is_staff or user.pk == self.owner_id))

    OWNER_EDITABLE = ("DRAFT", "PENDING", "REJECTED", "PUBLISHED")
    PUBLIC_STATUSES = ("PUBLISHED", "CANCELLED", "COMPLETED")

    def can_edit(self, user):
        """Owners edit their own live or in-progress events; staff manage all.
        Cancelled and completed events are frozen for owners."""
        if not (user and user.is_authenticated and user.is_active):
            return False
        if user.is_staff:
            return True
        return user.pk == self.owner_id and self.status in self.OWNER_EDITABLE

    @property
    def badge_class(self):
        """Tailwind classes for the status badge (kept in Python so the build sees them)."""
        return {
            "DRAFT": "bg-slate-200 text-slate-800",
            "PENDING": "bg-amber-100 text-amber-900",
            "PUBLISHED": "bg-emerald-100 text-emerald-900",
            "REJECTED": "bg-red-100 text-red-800",
            "CANCELLED": "bg-slate-300 text-slate-900",
            "COMPLETED": "bg-navy-100 text-navy-900",
        }[self.status]


class SavedEvent(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="saved_events")
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="saved_by")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(fields=["user", "event"], name="unique_saved_event_per_user")]

    def __str__(self):
        return f"{self.user} saved {self.event}"


class EventReport(models.Model):
    class Reason(models.TextChoices):
        SCAM = "SCAM", "Looks like a scam"
        INACCURATE = "INACCURATE", "Details are wrong"
        INAPPROPRIATE = "INAPPROPRIATE", "Inappropriate content"
        DUPLICATE = "DUPLICATE", "Duplicate listing"
        OTHER = "OTHER", "Something else"

    class Status(models.TextChoices):
        OPEN = "OPEN", "Open"
        RESOLVED = "RESOLVED", "Resolved"
        DISMISSED = "DISMISSED", "Dismissed"

    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="event_reports")
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="reports")
    reason = models.CharField(max_length=15, choices=Reason.choices)
    description = models.TextField(blank=True, max_length=2000)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN, db_index=True)
    handled_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="handled_reports")
    handled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            # One open report per person per event; they can report again after it's handled.
            models.UniqueConstraint(fields=["reporter", "event"], condition=Q(status="OPEN"), name="one_open_report_per_user_event"),
        ]

    def __str__(self):
        return f"Report on {self.event} ({self.get_reason_display()})"
