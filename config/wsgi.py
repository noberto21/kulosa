import os

from django.core.wsgi import get_wsgi_application

from config.deployment import migrate_vercel_database

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
application = get_wsgi_application()
migrate_vercel_database()
