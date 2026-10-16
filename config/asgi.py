import os

from django.core.asgi import get_asgi_application

from config.deployment import migrate_vercel_sqlite_database

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
application = get_asgi_application()
migrate_vercel_sqlite_database()
