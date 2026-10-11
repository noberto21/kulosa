"""Poster / logo upload hardening.

We don't trust the filename, extension or declared content type. Pillow must
be able to decode the bytes, the real format must be JPEG, PNG or WebP (no SVG,
GIF or anything scriptable), and the image is re-encoded under a random name so
EXIF metadata (including GPS location) is dropped.
"""
from io import BytesIO
from uuid import uuid4

from django import forms
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import InMemoryUploadedFile
from PIL import Image, ImageOps

MAX_BYTES = 5 * 1024 * 1024
MAX_DIMENSION = 6000
ALLOWED = {"JPEG": (".jpg", "image/jpeg"), "PNG": (".png", "image/png"), "WEBP": (".webp", "image/webp")}


def clean_image_upload(upload, field_name="image"):
    if upload.size > MAX_BYTES:
        raise ValidationError(f"This image is {upload.size / 1024 / 1024:.1f} MB. The limit is {MAX_BYTES // 1024 // 1024} MB.")
    try:
        upload.seek(0)
        img = Image.open(upload)
        fmt = img.format
        if fmt not in ALLOWED:
            raise ValidationError("Upload a JPEG, PNG or WebP image.")
        if max(img.size) > MAX_DIMENSION:
            raise ValidationError(f"The image is too large. Keep each side under {MAX_DIMENSION} pixels.")
        img.load()
    except ValidationError:
        raise
    except Exception:  # corrupt data, decompression bombs, unsupported files
        raise ValidationError("That file isn't a valid image. Upload a JPEG, PNG or WebP.")

    img = ImageOps.exif_transpose(img)
    buf = BytesIO()
    if fmt == "JPEG":
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        img.save(buf, "JPEG", quality=88, optimize=True)
    elif fmt == "PNG":
        img.save(buf, "PNG", optimize=True)
    else:
        img.save(buf, "WEBP", quality=88)
    ext, content_type = ALLOWED[fmt]
    buf.seek(0)
    return InMemoryUploadedFile(buf, field_name, f"{uuid4().hex}{ext}", content_type, buf.getbuffer().nbytes, None)


class SafeImageField(forms.ImageField):
    def to_python(self, data):
        f = super().to_python(data)  # Django's own Pillow verification first
        if f is None or not hasattr(f, "image"):
            return f
        return clean_image_upload(f, self.label or "image")
