from django import forms
from django.contrib import admin, messages
from django.db.models import Count, Q
from django.utils import timezone

from . import workflow
from .models import Category, Event, EventReport, OrganizerProfile, SavedEvent
from .notifications import send_review_result


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name",)


@admin.register(OrganizerProfile)
class OrganizerProfileAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "is_verified", "created_at")
    list_filter = ("is_verified",)
    search_fields = ("name", "owner__email")
    raw_id_fields = ("owner",)


class EventAdminForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = "__all__"

    def clean(self):
        data = super().clean()
        if data.get("status") == Event.Status.REJECTED and not (data.get("moderation_note") or "").strip():
            self.add_error("moderation_note", "Explain why the event was rejected so the organizer can fix it.")
        return data


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    form = EventAdminForm
    list_display = ("title", "category", "status", "start_datetime", "town", "owner", "submitted_at", "is_featured", "open_reports")
    list_filter = ("status", "category", "is_featured", "event_type", "county")
    search_fields = ("title", "summary", "owner__email", "venue_name")
    date_hierarchy = "start_datetime"
    readonly_fields = ("created_at", "updated_at", "submitted_at", "published_at", "reviewed_at", "reviewed_by")
    raw_id_fields = ("owner", "organizer")
    actions = ["approve_selected", "cancel_selected", "feature_selected", "unfeature_selected"]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            _open_reports=Count("reports", filter=Q(reports__status="OPEN"), distinct=True))

    @admin.display(description="Open reports", ordering="_open_reports")
    def open_reports(self, obj):
        return obj._open_reports

    @admin.action(description="Feature selected events on the homepage")
    def feature_selected(self, request, queryset):
        n = queryset.filter(status=Event.Status.PUBLISHED).update(is_featured=True)
        self.message_user(request, f"{n} published event(s) featured. Only published events can be featured.")

    @admin.action(description="Remove selected events from featured")
    def unfeature_selected(self, request, queryset):
        n = queryset.update(is_featured=False)
        self.message_user(request, f"{n} event(s) unfeatured.")

    @admin.action(description="Approve selected pending events")
    def approve_selected(self, request, queryset):
        done = skipped = 0
        for event in queryset.select_related("owner"):
            try:
                workflow.approve(event, request.user)
            except workflow.InvalidTransition:
                skipped += 1
                continue
            send_review_result(event)
            done += 1
        if done:
            self.message_user(request, f"{done} event(s) approved and organizers notified.", messages.SUCCESS)
        if skipped:
            self.message_user(request, f"{skipped} skipped: only pending events can be approved.", messages.WARNING)

    @admin.action(description="Cancel selected published events")
    def cancel_selected(self, request, queryset):
        done = skipped = 0
        for event in queryset:
            try:
                workflow.cancel(event, request.user)
                done += 1
            except workflow.InvalidTransition:
                skipped += 1
        if done:
            self.message_user(request, f"{done} event(s) cancelled.", messages.SUCCESS)
        if skipped:
            self.message_user(request, f"{skipped} skipped: only published events can be cancelled.", messages.WARNING)

    def save_model(self, request, obj, form, change):
        status_changed = change and "status" in form.changed_data
        if status_changed and obj.status in {Event.Status.PUBLISHED, Event.Status.REJECTED, Event.Status.CANCELLED}:
            obj.reviewed_by = request.user
            obj.reviewed_at = timezone.now()
        super().save_model(request, obj, form, change)
        if status_changed and obj.status in {Event.Status.PUBLISHED, Event.Status.REJECTED}:
            send_review_result(obj)


@admin.register(SavedEvent)
class SavedEventAdmin(admin.ModelAdmin):
    list_display = ("user", "event", "created_at")
    raw_id_fields = ("user", "event")


@admin.register(EventReport)
class EventReportAdmin(admin.ModelAdmin):
    list_display = ("event", "reason", "status", "reporter", "created_at", "handled_by")
    list_filter = ("status", "reason")
    search_fields = ("event__title", "reporter__email", "description")
    raw_id_fields = ("reporter", "event", "handled_by")
    readonly_fields = ("created_at", "handled_at")
    actions = ["mark_resolved", "mark_dismissed"]

    def _close(self, request, queryset, status, label):
        n = queryset.filter(status=EventReport.Status.OPEN).update(
            status=status, handled_by=request.user, handled_at=timezone.now())
        self.message_user(request, f"{n} report(s) marked {label}.")

    @admin.action(description="Mark selected open reports resolved (action was taken)")
    def mark_resolved(self, request, queryset):
        self._close(request, queryset, EventReport.Status.RESOLVED, "resolved")

    @admin.action(description="Dismiss selected open reports (no action needed)")
    def mark_dismissed(self, request, queryset):
        self._close(request, queryset, EventReport.Status.DISMISSED, "dismissed")

    def save_model(self, request, obj, form, change):
        if change and "status" in form.changed_data and obj.status != EventReport.Status.OPEN:
            obj.handled_by, obj.handled_at = request.user, timezone.now()
        super().save_model(request, obj, form, change)
