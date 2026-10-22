import logging

LOG_FORMAT = (
    "%(asctime)s %(levelname)s %(analysis_id)s %(step)s %(duration_ms)s %(outcome)s %(message)s"
)
_EXTRA_FIELDS = ("analysis_id", "step", "duration_ms", "outcome")


class _DefaultFieldsFilter(logging.Filter):
    """Fill the workflow fields with "-" so every record fits LOG_FORMAT."""

    def filter(self, record: logging.LogRecord) -> bool:
        for field in _EXTRA_FIELDS:
            if not hasattr(record, field):
                setattr(record, field, "-")
        return True


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    handler.addFilter(_DefaultFieldsFilter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())
