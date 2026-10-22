from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from eduvision.api import health
from eduvision.api.errors import register_error_handlers
from eduvision.config import get_settings
from eduvision.db.session import create_db_and_tables, create_db_engine
from eduvision.logging_config import configure_logging


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    engine = create_db_engine(get_settings().database_url)
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
    return app
