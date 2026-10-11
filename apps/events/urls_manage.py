from django.urls import path

from . import views_manage as v

app_name = "dashboard"

urlpatterns = [
    path("", v.my_events, name="list"),
    path("new/", v.event_create, name="create"),
    path("organizer/", v.organizer_edit, name="organizer"),
    path("<int:pk>/edit/", v.event_edit, name="edit"),
    path("<int:pk>/submit/", v.event_submit, name="submit"),
    path("<int:pk>/withdraw/", v.event_withdraw, name="withdraw"),
    path("<int:pk>/cancel/", v.event_cancel, name="cancel"),
    path("<int:pk>/delete/", v.event_delete, name="delete"),
]
