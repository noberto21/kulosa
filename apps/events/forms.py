from django import forms
from django.core.validators import URLValidator
from django.utils import timezone

from apps.accounts.forms import StyledFormMixin

from .constants import COUNTY_CHOICES
from .images import SafeImageField
from .models import Category, Event, EventReport, OrganizerProfile

DT_FORMAT = "%Y-%m-%dT%H:%M"
_http_only = URLValidator(schemes=["http", "https"])


def _dt_widget():
    return forms.DateTimeInput(format=DT_FORMAT, attrs={"type": "datetime-local"})


class EventForm(StyledFormMixin, forms.ModelForm):
    cover_image = SafeImageField(
        label="Poster", required=False,
        help_text="JPEG, PNG or WebP, up to 5 MB. Location data is removed from uploads.",
    )
    county = forms.ChoiceField(choices=COUNTY_CHOICES, required=False)
    booking_url = forms.URLField(
        label="Ticket or booking link", required=False, max_length=500, validators=[_http_only],
        help_text="Where people buy tickets or register. Must start with https:// or http://. KULOSA doesn't sell tickets.",
    )
    start_datetime = forms.DateTimeField(label="Starts", input_formats=[DT_FORMAT], widget=_dt_widget(),
                                         help_text="Kenya time (East Africa Time).")
    end_datetime = forms.DateTimeField(label="Ends", input_formats=[DT_FORMAT], widget=_dt_widget())

    class Meta:
        model = Event
        fields = [
            "title", "summary", "description", "category", "cover_image",
            "start_datetime", "end_datetime", "event_type",
            "venue_name", "address", "county", "town", "latitude", "longitude",
            "is_free", "ticket_price", "booking_url", "organizer",
        ]
        labels = {
            "title": "Event name", "summary": "Short summary", "description": "Full description",
            "event_type": "Event type", "venue_name": "Venue", "town": "Town or city",
            "latitude": "Latitude", "longitude": "Longitude",
            "is_free": "This event is free to attend", "ticket_price": "Ticket price (KES)",
        }
        help_texts = {
            "summary": "One line shown on event cards (up to 240 characters).",
            "venue_name": "In-person events need a venue name or an address (or both).",
            "latitude": "Optional. Both coordinates help us show a map later.",
            "ticket_price": "The lowest ticket price, in Kenyan shillings.",
        }
        widgets = {
            "description": forms.Textarea(attrs={"rows": 8}),
            "summary": forms.TextInput(),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields["category"].queryset = Category.objects.order_by("name")
        self.fields["category"].empty_label = "Select a category"
        if user is not None:
            qs = OrganizerProfile.objects.filter(owner=user)
            if qs.exists():
                self.fields["organizer"].queryset = qs
                self.fields["organizer"].empty_label = "Don't link an organizer profile"
                self.fields["organizer"].required = False
            else:
                del self.fields["organizer"]
        self._old_image = self.instance.cover_image.name if self.instance.pk else ""

    def clean(self):
        data = super().clean()
        end = data.get("end_datetime")
        if self.data.get("action") == "submit" and end and end <= timezone.now():
            self.add_error("end_datetime", "This event has already ended. Choose a future date to submit it.")
        return data

    def delete_replaced_image(self, event):
        """Remove the previous poster file once a new one (or none) has been saved."""
        if self._old_image and self._old_image != event.cover_image.name:
            event.cover_image.storage.delete(self._old_image)


class OrganizerProfileForm(StyledFormMixin, forms.ModelForm):
    logo = SafeImageField(required=False, help_text="JPEG, PNG or WebP, up to 5 MB.")
    website = forms.URLField(required=False, validators=[_http_only])

    class Meta:
        model = OrganizerProfile
        fields = ["name", "logo", "description", "contact_email", "contact_phone", "website"]
        labels = {"name": "Organization or organizer name", "contact_email": "Public contact email", "contact_phone": "Public contact phone"}
        help_texts = {"contact_email": "Shown on your events. Leave empty to keep it private."}
        widgets = {"description": forms.Textarea(attrs={"rows": 5})}


class ReportForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = EventReport
        fields = ["reason", "description"]
        labels = {"reason": "What's wrong with this listing?", "description": "Details"}
        help_texts = {"description": "Tell the reviewers what you noticed. Don't include private information."}
        widgets = {"description": forms.Textarea(attrs={"rows": 5})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["reason"].choices = [("", "Choose a reason")] + list(EventReport.Reason.choices)

    def clean(self):
        data = super().clean()
        if data.get("reason") == EventReport.Reason.OTHER and not (data.get("description") or "").strip():
            self.add_error("description", "Please describe the problem.")
        return data
