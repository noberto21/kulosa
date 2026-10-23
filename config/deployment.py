import os


def migrate_vercel_database():
    if not os.environ.get("VERCEL"):
        return

    from django.core.management import call_command

    # Run idempotent migrations on cold starts for either SQLite or PostgreSQL.
    # PostgreSQL has no local database file to inspect, and skipping migrations
    # when a SQLite file exists would leave new deployments behind.
    call_command("migrate", interactive=False, verbosity=0)
