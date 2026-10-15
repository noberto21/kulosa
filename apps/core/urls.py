from django.urls import path
from django.views.generic import RedirectView

from . import views

app_name = "core"

urlpatterns = [
    path("", views.home, name="home"),
    path("categories/", views.categories, name="categories"),
    path("about/", views.about, name="about"),
    path("terms/", views.terms, name="terms"),
    # Not built yet: these render an honest "coming soon" page.
    path("share-event/", RedirectView.as_view(pattern_name="dashboard:create"), name="share_event"),
    path("contact/", views.coming_soon, {"feature": "Contact"}, name="contact"),
    path("privacy/", views.coming_soon, {"feature": "Privacy policy"}, name="privacy"),
]
