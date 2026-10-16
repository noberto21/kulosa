import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
application = get_wsgi_application()

if os.environ.get("VERCEL") and not os.environ.get("DATABASE_URL"):
    from pathlib import Path

    from django.conf import settings
    from django.core.management import call_command

    database_path = Path(settings.DATABASES["default"]["NAME"])
    if not database_path.exists():
        call_command("migrate", interactive=False, verbosity=0)
