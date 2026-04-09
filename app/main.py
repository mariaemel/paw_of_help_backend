from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.db.base import Base
from app.db.seed import seed_animals_if_empty
from app.db.session import SessionLocal, engine
from app.modules.animals.router import router as animals_router
from app.modules.auth.router import router as auth_router

# Import models so SQLAlchemy metadata contains all tables.
from app import models  # noqa: F401


app = FastAPI(title=settings.app_name)
Path(settings.media_dir).mkdir(parents=True, exist_ok=True)


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)
    if settings.seed_demo_data:
        db = SessionLocal()
        try:
            seed_animals_if_empty(db)
        finally:
            db.close()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(auth_router, prefix=settings.api_prefix)
app.include_router(animals_router, prefix=settings.api_prefix)
app.mount(settings.media_url_prefix, StaticFiles(directory=settings.media_dir), name="media")
