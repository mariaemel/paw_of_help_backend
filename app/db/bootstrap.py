from alembic import command
from alembic.config import Config
from sqlalchemy.engine import Engine

from app.core.config import settings
from app.db.base import Base
from app.db.migrate import ensure_sqlite_schema
from app.db.session import SessionLocal
from app.modules.account.repository import AccountRepository


def _alembic_config() -> Config:
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", settings.database_url)
    return cfg


def run_migrations() -> None:
    command.upgrade(_alembic_config(), "head")


def _merge_duplicate_org_chat_dialogs() -> None:
    db = SessionLocal()
    try:
        removed = AccountRepository(db).merge_duplicate_org_chat_dialogs()
        if removed:
            db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_db(engine: Engine) -> None:
    import app.models  # noqa: F401

    if engine.dialect.name == "sqlite":
        Base.metadata.create_all(bind=engine)
        ensure_sqlite_schema(engine)
    else:
        run_migrations()
    _merge_duplicate_org_chat_dialogs()
