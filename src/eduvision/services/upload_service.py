from eduvision.db.models import Upload
from eduvision.db.repositories import UploadRepository
from eduvision.storage.local_storage import LocalStorage

# Content signature ("magic bytes") -> (content type, file extension).
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_JPEG_SIGNATURE = b"\xff\xd8\xff"


class UnsupportedMediaTypeError(Exception):
    """The file content is not a JPEG, PNG or WebP image."""


class FileTooLargeError(Exception):
    """The file exceeds the configured maximum size."""


def detect_image_type(data: bytes) -> tuple[str, str] | None:
    """Return (content_type, extension) based on the file's signature, or None if unsupported."""
    if data.startswith(_JPEG_SIGNATURE):
        return "image/jpeg", "jpg"
    if data.startswith(_PNG_SIGNATURE):
        return "image/png", "png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp", "webp"
    return None


def _display_name(filename: str | None) -> str:
    """Strip any directory part from the client-supplied name (for display only)."""
    name = (filename or "").replace("\\", "/").rsplit("/", 1)[-1].strip()
    return name or "upload"


class UploadService:
    def __init__(
        self, uploads: UploadRepository, storage: LocalStorage, max_upload_bytes: int
    ) -> None:
        self._uploads = uploads
        self._storage = storage
        self.max_upload_bytes = max_upload_bytes

    def create_upload(self, filename: str | None, data: bytes) -> Upload:
        if len(data) > self.max_upload_bytes:
            raise FileTooLargeError(
                f"File is larger than the {self.max_upload_bytes // (1024 * 1024)} MB limit."
            )
        detected = detect_image_type(data)
        if detected is None:
            raise UnsupportedMediaTypeError("Only JPEG, PNG and WebP images are supported.")
        content_type, extension = detected

        stored_filename = self._storage.save(data, extension)
        return self._uploads.create(
            Upload(
                original_filename=_display_name(filename),
                stored_filename=stored_filename,
                content_type=content_type,
                size_bytes=len(data),
            )
        )
