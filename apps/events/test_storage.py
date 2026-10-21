from types import SimpleNamespace
from unittest import mock

from django.core.exceptions import SuspiciousFileOperation
from django.core.files.base import ContentFile
from django.test import SimpleTestCase

from .storage import VercelBlobStorage, public_image_url


class VercelBlobStorageTests(SimpleTestCase):
    def setUp(self):
        self.storage = VercelBlobStorage()
        self.blob = mock.Mock()
        self.storage._blob = mock.Mock(return_value=self.blob)

    def test_save_uploads_public_blob_and_returns_delivery_url(self):
        self.blob.put_blob.return_value = SimpleNamespace(url="https://store.public.blob.vercel-storage.com/poster.png")

        saved = self.storage.save("events/posters/poster.png", ContentFile(b"image"))

        self.assertEqual(saved, "https://store.public.blob.vercel-storage.com/poster.png")
        self.blob.put_blob.assert_called_once_with(
            "events/posters/poster.png",
            b"image",
            access="public",
            content_type="image/png",
            add_random_suffix=True,
        )

    def test_open_reads_blob_content(self):
        url = "https://store.public.blob.vercel-storage.com/poster.png"
        self.blob.get_blob.return_value = SimpleNamespace(body=b"image")

        with self.storage.open(url) as image:
            self.assertEqual(image.read(), b"image")

        self.blob.get_blob.assert_called_once_with(url, access="public")

    def test_delete_removes_blob(self):
        url = "https://store.public.blob.vercel-storage.com/poster.png"

        self.storage.delete(url)

        self.blob.delete_blob.assert_called_once_with(url)

    def test_delete_skips_legacy_local_image_reference(self):
        self.storage.delete("events/posters/old-poster.png")

        self.blob.delete_blob.assert_not_called()

    def test_legacy_image_reference_has_no_public_url(self):
        image = SimpleNamespace(name="events/posters/old-poster.png", storage=self.storage)

        self.assertEqual(public_image_url(image), "")

    def test_blob_image_reference_has_public_url(self):
        url = "https://store.public.blob.vercel-storage.com/poster.png"
        image = SimpleNamespace(name=url, storage=self.storage, url=url)

        self.assertEqual(public_image_url(image), url)

    def test_save_rejects_path_traversal(self):
        with self.assertRaises(SuspiciousFileOperation):
            self.storage.save("../poster.png", ContentFile(b"image"))
