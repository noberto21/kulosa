"""Django storage backend for public Vercel Blob event images."""
import mimetypes

from django.core.exceptions import ImproperlyConfigured, SuspiciousFileOperation
from django.core.files.base import ContentFile
from django.core.files.storage import Storage
from django.core.files.utils import validate_file_name


class VercelBlobStorage(Storage):
    def get_available_name(self, name, max_length=None):
        name = str(name).replace("\\", "/")
        validate_file_name(name, allow_relative_path=True)
        if max_length is not None and len(name) > max_length:
            raise SuspiciousFileOperation(
                f"The file name is longer than the maximum length of {max_length}."
            )
        return name

    def _blob(self):
        try:
            from vercel.blob import sync as blob
        except ImportError as exc:
            raise ImproperlyConfigured(
                "Install the vercel-blob package to use Vercel Blob storage."
            ) from exc
        return blob

    def _save(self, name, content):
        content.seek(0)
        uploaded = self._blob().put_blob(
            name,
            content.read(),
            access="public",
            content_type=mimetypes.guess_type(name)[0] or "application/octet-stream",
            add_random_suffix=True,
        )
        return uploaded.url

    def _open(self, name, mode="rb"):
        if mode != "rb":
            raise ValueError("Vercel Blob files can only be opened in binary read mode.")
        result = self._blob().get_blob(name, access="public")
        return ContentFile(result.body, name=name)

    def delete(self, name):
        self._blob().delete_blob(name)

    def url(self, name):
        if not name.startswith("https://"):
            raise ValueError("Vercel Blob storage expects an HTTPS delivery URL.")
        return name
