from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from langchain_core.language_models import BaseChatModel
from sqlmodel import Session

from eduvision.api.errors import AppError
from eduvision.config import Settings, get_settings
from eduvision.db.repositories import AnalysisRepository, UploadRepository
from eduvision.db.session import get_session
from eduvision.schemas.analysis import (
    AnalysisListResponse,
    AnalysisResponse,
    CreateAnalysisRequest,
)
from eduvision.services.analysis_service import (
    AnalysisFailedError,
    AnalysisNotFoundError,
    AnalysisService,
    UploadNotFoundError,
)
from eduvision.storage.local_storage import LocalStorage

router = APIRouter(prefix="/api/v1")

# Failure reasons that are not a plain 500.
_FAILURE_STATUS = {"no_text_found": 422, "llm_unavailable": 502}


def get_chat_model(request: Request) -> BaseChatModel:
    model = request.app.state.chat_model
    if model is None:
        raise RuntimeError(
            "LLM_PROVIDER=fake needs a fake model injected via dependency_overrides."
        )
    assert isinstance(model, BaseChatModel)
    return model


def get_analysis_service(
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AnalysisService:
    return AnalysisService(
        UploadRepository(session),
        AnalysisRepository(session),
        LocalStorage(settings.upload_dir),
        settings.workflow_recursion_limit,
    )


ServiceDep = Annotated[AnalysisService, Depends(get_analysis_service)]


# `def`, not `async def`: the workflow and LLM calls are blocking, so FastAPI runs them in a
# threadpool instead of stalling the event loop.
@router.post("/analyses", status_code=201, response_model=AnalysisResponse)
def create_analysis(
    body: CreateAnalysisRequest,
    service: ServiceDep,
    model: Annotated[BaseChatModel, Depends(get_chat_model)],
) -> AnalysisResponse:
    try:
        analysis = service.create_analysis(body.upload_id, model)
    except UploadNotFoundError as exc:
        raise AppError(404, "upload_not_found", str(exc)) from exc
    except AnalysisFailedError as exc:
        status = _FAILURE_STATUS.get(exc.failure_reason, 500)
        raise AppError(status, exc.failure_reason, exc.message, exc.analysis_id) from exc
    return AnalysisResponse.from_model(analysis)


@router.get("/analyses/{analysis_id}", response_model=AnalysisResponse)
def get_analysis(analysis_id: str, service: ServiceDep) -> AnalysisResponse:
    try:
        return AnalysisResponse.from_model(service.get_analysis(analysis_id))
    except AnalysisNotFoundError as exc:
        raise AppError(404, "analysis_not_found", str(exc)) from exc


@router.get("/analyses", response_model=AnalysisListResponse)
def list_analyses(
    service: ServiceDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AnalysisListResponse:
    items, total = service.list_analyses(limit, offset)
    return AnalysisListResponse(
        items=[AnalysisResponse.from_model(a) for a in items],
        total=total,
        limit=limit,
        offset=offset,
    )
