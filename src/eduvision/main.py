from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from eduvision.api import analyses, health, uploads
from eduvision.api.errors import register_error_handlers
from eduvision.config import get_settings
from eduvision.db.session import create_db_and_tables, create_db_engine
from eduvision.llm.factory import create_chat_model
from eduvision.logging_config import configure_logging


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    # Built once at startup so a missing LLM_MODEL / ANTHROPIC_API_KEY fails here, not on a
    # request. The fake provider has no model in src/: tests inject theirs.
    app.state.chat_model = None if settings.llm_provider == "fake" else create_chat_model(settings)
    engine = create_db_engine(settings.database_url)
    create_db_and_tables(engine)
    app.state.engine = engine
    yield
    engine.dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(title="EduVision", lifespan=lifespan)
    register_error_handlers(app)
    app.include_router(health.router)
    app.include_router(uploads.router)
    app.include_router(analyses.router)
    return app
