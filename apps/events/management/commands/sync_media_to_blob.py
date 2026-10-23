import mimetypes

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from vercel.blob import sync as blob


class Command(BaseCommand):
    help = "Upload files under MEDIA_ROOT to the connected public Vercel Blob store."

    def handle(self, *args, **options):
        store_id = getattr(settings, "BLOB_STORE_ID", "")
        if not store_id:
            raise CommandError("Set BLOB_STORE_ID and connect a Vercel Blob store before syncing media.")

        media_root = settings.MEDIA_ROOT
        files = sorted(path for path in media_root.rglob("*") if path.is_file())
        for path in files:
            name = path.relative_to(media_root).as_posix()
            content_type, _ = mimetypes.guess_type(name)
            with path.open("rb") as content:
                blob.put_blob(
                    name,
                    content,
                    access="public",
                    content_length=path.stat().st_size,
                    content_type=content_type,
                    allow_overwrite=True,
                )
            self.stdout.write(f"Uploaded {name}")

        self.stdout.write(self.style.SUCCESS(f"{len(files)} media file(s) synced."))
