import json

from django.utils import timezone
from django.utils.safestring import mark_safe

_MODES = {"PHYSICAL": "OfflineEventAttendanceMode", "ONLINE": "OnlineEventAttendanceMode", "HYBRID": "MixedEventAttendanceMode"}


def event_jsonld(event, url, image_url=""):
    """schema.org Event data for search engines, safe to embed in a <script> tag."""
    data = {
        "@context": "https://schema.org",
        "@type": "Event",
        "name": event.title,
        "description": event.summary,
        "url": url,
        "startDate": timezone.localtime(event.start_datetime).isoformat(),
        "endDate": timezone.localtime(event.end_datetime).isoformat(),
        "eventStatus": "https://schema.org/EventCancelled" if event.is_cancelled else "https://schema.org/EventScheduled",
        "eventAttendanceMode": "https://schema.org/" + _MODES[event.event_type],
    }
    if image_url:
        data["image"] = [image_url]
    place = {"@type": "Place", "name": event.venue_name or event.town or event.county,
             "address": {"@type": "PostalAddress", "streetAddress": event.address, "addressLocality": event.town,
                         "addressRegion": event.county, "addressCountry": "KE"}}
    if event.event_type == "ONLINE":
        data["location"] = {"@type": "VirtualLocation", "url": event.booking_url or url}
    elif event.event_type == "HYBRID":
        data["location"] = [place, {"@type": "VirtualLocation", "url": event.booking_url or url}]
    else:
        data["location"] = place
    if event.is_free or event.ticket_price is not None:
        data["offers"] = {"@type": "Offer", "price": "0" if event.is_free else str(event.ticket_price),
                          "priceCurrency": event.currency, "url": event.booking_url or url}
    if event.organizer_id:
        data["organizer"] = {"@type": "Organization", "name": event.organizer.name}
    text = json.dumps(data, ensure_ascii=False)
    # Make it impossible for user text to close the script tag.
    return mark_safe(text.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026"))
