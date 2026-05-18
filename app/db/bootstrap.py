from alembic import command
from alembic.config import Config
from sqlalchemy.engine import Engine

from app.core.config import settings
from app.db.base import Base
from app.db.migrate import ensure_sqlite_schema


def _alembic_config() -> Config:
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", settings.database_url)
    return cfg


def run_migrations() -> None:
    command.upgrade(_alembic_config(), "head")


def init_db(engine: Engine) -> None:
    import app.models  # noqa: F401

    if engine.dialect.name == "sqlite":
        Base.metadata.create_all(bind=engine)
        ensure_sqlite_schema(engine)
    else:
        run_migrations()
