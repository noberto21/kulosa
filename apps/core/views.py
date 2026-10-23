from django.http import HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from apps.events import services


def home(request):
    return render(request, "core/home.html", {
        "categories": services.popular_categories(8),
        "when_choices": services.WHEN_CHOICES,
        "featured": services.featured(),
        "trending": services.trending(),
        "today": services.happening_today(),
        "this_week": services.coming_this_week(),
        "recent": services.recently_added(),
        "site_has_events": services.live().exists(),
    })


def categories(request):
    return render(request, "core/categories.html", {"categories": services.categories_with_counts()})


def about(request):
    return render(request, "core/about.html")


def terms(request):
    return render(request, "core/terms.html")


def privacy(request):
    return render(request, "core/privacy.html")


def coming_soon(request, feature):
    return render(request, "core/coming_soon.html", {"feature": feature}, status=200)


@require_GET
def robots(request):
    lines = [
        "User-agent: *",
        "Disallow: /admin/",
        "Disallow: /my-events/",
        "Disallow: /account/",
        "Disallow: /saved/",
        "Disallow: /login/",
        "Disallow: /register/",
        "Disallow: /password-reset/",
        "",
        f"Sitemap: {request.build_absolute_uri('/sitemap.xml')}",
    ]
    return HttpResponse("\n".join(lines) + "\n", content_type="text/plain")
