from collections.abc import Iterator
from pathlib import Path

from fastapi import Request
from sqlalchemy.engine import Engine, make_url
from sqlmodel import Session, SQLModel, create_engine

from eduvision.db import models  # noqa: F401  (registers tables on SQLModel.metadata)


def create_db_engine(database_url: str) -> Engine:
    url = make_url(database_url)
    connect_args: dict[str, bool] = {}
    if url.get_backend_name() == "sqlite":
        connect_args["check_same_thread"] = False
        if url.database and url.database != ":memory:":
            Path(url.database).parent.mkdir(parents=True, exist_ok=True)
    return create_engine(database_url, connect_args=connect_args)


def create_db_and_tables(engine: Engine) -> None:
    SQLModel.metadata.create_all(engine)


def get_session(request: Request) -> Iterator[Session]:
    with Session(request.app.state.engine) as session:
        yield session
