import os


def site(request):
    return {
        "SITE_NAME": "KULOSA",
        "TAGLINE": "Discover. Share. Experience.",
        "vercel_analytics_enabled": bool(os.environ.get("VERCEL")),
    }
