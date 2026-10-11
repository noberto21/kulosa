from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from .models import Event


class EventSitemap(Sitemap):
    changefreq = "daily"
    priority = 0.8

    def items(self):
        return Event.objects.published().upcoming().order_by("start_datetime")

    def lastmod(self, obj):
        return obj.updated_at


class StaticSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.5

    def items(self):
        return ["core:home", "events:explore", "core:categories", "core:about"]

    def location(self, item):
        return reverse(item)
