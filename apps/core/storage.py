from re import fullmatch
from urllib.parse import quote

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.files.base import ContentFile
from django.core.files.storage import Storage
from vercel.blob import sync as blob


class VercelBlobStorage(Storage):
    access = "public"

    @property
    def store_id(self):
        store_id = settings.BLOB_STORE_ID.removeprefix("store_")
        if not fullmatch(r"[A-Za-z0-9_-]+", store_id):
            raise ImproperlyConfigured("BLOB_STORE_ID is not a valid Vercel Blob store ID.")
        return store_id

    def _save(self, name, content):
        uploaded = blob.put_blob(
            name,
            content.chunks(),
            access=self.access,
            content_length=content.size,
            content_type=getattr(content, "content_type", None),
            add_random_suffix=False,
        )
        return uploaded.pathname

    def _open(self, name, mode="rb"):
        if mode != "rb":
            raise ValueError("Vercel Blob files can only be opened in binary read mode.")
        downloaded = blob.get_blob(name, access=self.access)
        return ContentFile(downloaded.body, name=name)

    def delete(self, name):
        blob.delete_blob(name)

    def exists(self, name):
        try:
            blob.head_blob(name)
        except blob.BlobNotFoundError:
            return False
        return True

    def size(self, name):
        return blob.head_blob(name).size

    def url(self, name):
        if name.startswith(("https://", "http://")):
            return name
        return (
            f"https://{self.store_id}.public.blob.vercel-storage.com/"
            f"{quote(name, safe='/')}"
        )
