from fastapi import FastAPI

from eduvision.api import health
from eduvision.api.errors import register_error_handlers
from eduvision.config import get_settings
from eduvision.logging_config import configure_logging


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(title="EduVision")
    register_error_handlers(app)
    app.include_router(health.router)
    return app
