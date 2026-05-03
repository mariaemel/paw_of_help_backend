from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.db.base import Base
from app.db.migrate import ensure_sqlite_schema
from app.db.seed import seed_demo_data_if_empty
from app.db.session import SessionLocal, engine
from app.modules.account.router import router as account_router
from app.modules.animals.router import router as animals_router
from app.modules.auth.router import router as auth_router
from app.modules.events.router import router as events_router
from app.modules.knowledge.router import router as knowledge_router
from app.modules.organizations.router import router as organizations_router
from app.modules.urgent.router import router as urgent_router
from app.modules.volunteers.router import router as volunteers_router
from app.modules.help.router import router as help_router

from app import models


app = FastAPI(title=settings.app_name)
Path(settings.media_dir).mkdir(parents=True, exist_ok=True)

_cors_origins = [x.strip() for x in settings.cors_origins.split(",") if x.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    ensure_sqlite_schema(engine)
    Base.metadata.create_all(bind=engine)
    if settings.seed_demo_data:
        db = SessionLocal()
        try:
            seed_demo_data_if_empty(db)
        finally:
            db.close()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(auth_router, prefix=settings.api_prefix)
app.include_router(account_router, prefix=settings.api_prefix)
app.include_router(animals_router, prefix=settings.api_prefix)
app.include_router(organizations_router, prefix=settings.api_prefix)
app.include_router(volunteers_router, prefix=settings.api_prefix)
app.include_router(knowledge_router, prefix=settings.api_prefix)
app.include_router(events_router, prefix=settings.api_prefix)
app.include_router(urgent_router, prefix=settings.api_prefix)
app.include_router(help_router, prefix=settings.api_prefix)
app.mount(settings.media_url_prefix, StaticFiles(directory=settings.media_dir), name="media")
