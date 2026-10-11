from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path

from apps.core import views as core_views
from apps.events import views as event_views
from apps.events.sitemaps import EventSitemap, StaticSitemap

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("apps.accounts.urls")),
    path("my-events/", include("apps.events.urls_manage")),
    path("events/", include("apps.events.urls")),
    path("saved/", event_views.saved_events, name="saved_events"),
    path("organizers/<slug:slug>/", event_views.organizer_public, name="organizer_public"),
    path("sitemap.xml", sitemap, {"sitemaps": {"events": EventSitemap, "pages": StaticSitemap}}, name="sitemap"),
    path("robots.txt", core_views.robots, name="robots"),
    path("", include("apps.core.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
