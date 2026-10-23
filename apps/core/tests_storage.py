from types import SimpleNamespace
from unittest import mock

from django.core.files.base import ContentFile
from django.test import SimpleTestCase, override_settings
from vercel.blob import sync as blob

from .storage import VercelBlobStorage


@override_settings(BLOB_STORE_ID="store_example")
class VercelBlobStorageTests(SimpleTestCase):
    def setUp(self):
        self.storage = VercelBlobStorage()

    def test_url_uses_public_blob_domain_and_preserves_existing_blob_urls(self):
        self.assertEqual(
            self.storage.url("events/posters/poster.png"),
            "https://example.public.blob.vercel-storage.com/events/posters/poster.png",
        )
        existing_url = "https://another.public.blob.vercel-storage.com/poster.png"
        self.assertEqual(self.storage.url(existing_url), existing_url)

    @mock.patch("apps.core.storage.blob.put_blob")
    def test_save_uploads_file_and_returns_blob_path(self, put_blob):
        put_blob.return_value = SimpleNamespace(pathname="events/posters/poster.png")
        content = ContentFile(b"image", name="poster.png")

        saved_name = self.storage._save("events/posters/poster.png", content)

        self.assertEqual(saved_name, "events/posters/poster.png")
        put_blob.assert_called_once()
        self.assertEqual(put_blob.call_args.args[0], "events/posters/poster.png")
        self.assertEqual(put_blob.call_args.kwargs["content_length"], 5)
        self.assertEqual(put_blob.call_args.kwargs["access"], "public")

    @mock.patch("apps.core.storage.blob.head_blob")
    def test_exists_returns_false_only_when_blob_is_missing(self, head_blob):
        head_blob.side_effect = blob.BlobNotFoundError("missing")
        self.assertFalse(self.storage.exists("missing.png"))

        head_blob.side_effect = RuntimeError("service unavailable")
        with self.assertRaisesMessage(RuntimeError, "service unavailable"):
            self.storage.exists("poster.png")
