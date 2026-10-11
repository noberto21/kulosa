from django.urls import path

from . import views

app_name = "events"

urlpatterns = [
    path("", views.explore, name="explore"),
    path("<slug:slug>/", views.detail, name="detail"),
    path("<slug:slug>/save/", views.save_event, name="save"),
    path("<slug:slug>/unsave/", views.unsave_event, name="unsave"),
    path("<slug:slug>/report/", views.report_event, name="report"),
]
