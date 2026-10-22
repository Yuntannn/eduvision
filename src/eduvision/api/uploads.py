from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile
from sqlmodel import Session

from eduvision.api.errors import AppError
from eduvision.config import Settings, get_settings
from eduvision.db.repositories import UploadRepository
from eduvision.db.session import get_session
from eduvision.schemas.upload import UploadResponse
from eduvision.services.upload_service import (
    FileTooLargeError,
    UnsupportedMediaTypeError,
    UploadService,
)
from eduvision.storage.local_storage import LocalStorage

router = APIRouter(prefix="/api/v1")


def get_upload_service(
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> UploadService:
    return UploadService(
        UploadRepository(session), LocalStorage(settings.upload_dir), settings.max_upload_bytes
    )


@router.post("/uploads", status_code=201, response_model=UploadResponse)
async def create_upload(
    file: Annotated[UploadFile, File()],
    service: Annotated[UploadService, Depends(get_upload_service)],
) -> UploadResponse:
    # Read one byte past the limit so oversized files are detected without loading them fully.
    data = await file.read(service.max_upload_bytes + 1)
    try:
        upload = service.create_upload(file.filename, data)
    except FileTooLargeError as exc:
        raise AppError(413, "payload_too_large", str(exc)) from exc
    except UnsupportedMediaTypeError as exc:
        raise AppError(415, "unsupported_media_type", str(exc)) from exc
    return UploadResponse(
        upload_id=upload.id,
        original_filename=upload.original_filename,
        content_type=upload.content_type,
        size_bytes=upload.size_bytes,
        created_at=upload.created_at,
    )
