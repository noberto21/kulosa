import os
from pathlib import Path


def migrate_vercel_sqlite_database():
    if not os.environ.get("VERCEL"):
        return

    from django.conf import settings
    from django.core.management import call_command

    database_path = Path(settings.DATABASES["default"]["NAME"])
    if not database_path.exists():
        call_command("migrate", interactive=False, verbosity=0)
