from __future__ import annotations

import os
from pathlib import Path
from typing import Generator

from sqlmodel import Session, create_engine

from app.settings import settings


def _ensure_sqlite_dir(database_url: str) -> None:
    if not database_url.startswith("sqlite:///"):
        return
    # sqlite:///./data/app.db -> ./data/app.db
    path = database_url.replace("sqlite:///", "", 1)
    if path.startswith("./") or path.startswith(".\\"):
        p = Path(path)
    else:
        p = Path(path)
    if p.parent and str(p.parent) not in ("", "."):
        os.makedirs(p.parent, exist_ok=True)


_ensure_sqlite_dir(settings.database_url)

engine = create_engine(
    settings.database_url,
    echo=False,
    connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {},
)


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session

