from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import admin, public
from app.db.init_db import init_db, seed_default_factors, seed_default_weight_presets
from app.db.session import engine
from app.jobs.scheduler import start_scheduler
from app.settings import settings
from sqlmodel import Session

load_dotenv()


def create_app() -> FastAPI:
    app = FastAPI(title="Stock Ranking API", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def root_health() -> dict:
        return {"status": "ok"}

    app.include_router(public.router)
    app.include_router(admin.router)

    @app.on_event("startup")
    async def _startup() -> None:
        init_db()
        with Session(engine) as session:
            seed_default_factors(session)
            seed_default_weight_presets(session)
        start_scheduler()

    return app


app = create_app()

