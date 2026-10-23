"""KULOSA settings (Phase 1)."""
import os
import sys
from urllib.parse import parse_qsl, unquote, urlparse
from pathlib import Path
from urllib.parse import urlsplit

from django.core.exceptions import ImproperlyConfigured


try:
    from dotenv import load_dotenv
except ImportError:  # python-dotenv is optional at runtime
    load_dotenv = None

BASE_DIR = Path(__file__).resolve().parent.parent
if load_dotenv:
    load_dotenv(BASE_DIR / ".env")


def env_bool(name, default=False):
    return os.environ.get(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


DEBUG = env_bool("DJANGO_DEBUG", False)
IS_VERCEL = any(os.environ.get(name) for name in ("VERCEL", "VERCEL_ENV", "VERCEL_URL"))
if IS_VERCEL and DEBUG:
    raise ImproperlyConfigured("DJANGO_DEBUG must be false on Vercel.")

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    if DEBUG:
        # Development-only key so the project starts without a .env file.
        SECRET_KEY = "dev-only-insecure-key-do-not-use-in-production"
    else:
        raise ImproperlyConfigured("Set DJANGO_SECRET_KEY in your environment or .env file.")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sitemaps",
    "apps.core",
    "apps.accounts",
    "apps.events",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

AUTH_USER_MODEL = "accounts.User"
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "accounts:account"
LOGOUT_REDIRECT_URL = "core:home"

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.core.context_processors.site",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# Prefer a managed PostgreSQL database in production. Vercel Postgres and most
# providers expose a PostgreSQL connection URL as DATABASE_URL or POSTGRES_URL.
DATABASE_URL = os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL")
if IS_VERCEL and not DATABASE_URL:
    raise ImproperlyConfigured(
        "Set DATABASE_URL or POSTGRES_URL to a persistent PostgreSQL database before deploying to Vercel."
    )

if DATABASE_URL:
    parsed_database_url = urlparse(DATABASE_URL)
    if parsed_database_url.scheme not in {"postgres", "postgresql"}:
        raise ImproperlyConfigured("DATABASE_URL must use the postgres:// or postgresql:// scheme.")
    database_options = dict(parse_qsl(parsed_database_url.query))
    if IS_VERCEL:
        database_options.setdefault("sslmode", "require")
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": unquote(parsed_database_url.path.lstrip("/")),
            "USER": unquote(parsed_database_url.username or ""),
            "PASSWORD": unquote(parsed_database_url.password or ""),
            "HOST": parsed_database_url.hostname or "",
            "PORT": parsed_database_url.port or "",
            "OPTIONS": database_options,
            "CONN_MAX_AGE": 0 if IS_VERCEL else 60,
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": os.environ.get("DJANGO_DB_PATH")
            or BASE_DIR / "db.sqlite3",
            "OPTIONS": {"timeout": 20},  # wait up to 20s if another request holds the write lock
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en"
TIME_ZONE = "Africa/Nairobi"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
if os.environ.get("VERCEL") or os.environ.get("VERCEL_ENV") or os.environ.get("VERCEL_URL"):
    MEDIA_ROOT = Path("/tmp/kulosa-media")
else:
    MEDIA_ROOT = Path(os.environ.get("DJANGO_MEDIA_ROOT") or BASE_DIR / "media")

if IS_VERCEL:
    if not (
        os.environ.get("BLOB_READ_WRITE_TOKEN")
        or os.environ.get("VERCEL_BLOB_READ_WRITE_TOKEN")
        or os.environ.get("BLOB_STORE_ID")
    ):
        raise ImproperlyConfigured(
            "Connect a Vercel Blob store before deploying. It must provide BLOB_READ_WRITE_TOKEN or BLOB_STORE_ID."
        )
    STORAGES = {
        "default": {"BACKEND": "apps.events.storage.VercelBlobStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }

# Email: prints password-reset emails to the console in development.
EMAIL_BACKEND = os.environ.get("DJANGO_EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = os.environ.get("EMAIL_HOST", "localhost")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "25"))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", False)
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "KULOSA <no-reply@localhost>")
VERCEL_SITE_HOST = os.environ.get("VERCEL_PROJECT_PRODUCTION_URL") or os.environ.get("VERCEL_URL")
SITE_URL = os.environ.get(
    "SITE_URL",
    f"https://{VERCEL_SITE_HOST}" if VERCEL_SITE_HOST else "http://127.0.0.1:8000",
)  # used in emails
# Staff who get an email for each new submission and report (comma separated; empty = no emails).
MODERATOR_EMAILS = [e.strip() for e in os.environ.get("MODERATOR_EMAILS", "").split(",") if e.strip()]
PASSWORD_RESET_TIMEOUT = 60 * 60 * 3  # reset links last 3 hours

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

if not DEBUG:
    SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", True)
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_CONTENT_TYPE_NOSNIFF = True

# Faster password hashing ONLY when running the test suite.
if "test" in sys.argv[1:2]:
    PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get(
        "DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1"
    ).split(",")
    if host.strip()
] + [
    os.environ[name]
    for name in ("VERCEL_URL", "VERCEL_PROJECT_PRODUCTION_URL")
    if os.environ.get(name)
]

CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",")
    if origin.strip()
] + [
    f"https://{os.environ[name]}"
    for name in ("VERCEL_URL", "VERCEL_PROJECT_PRODUCTION_URL")
    if os.environ.get(name)
]
