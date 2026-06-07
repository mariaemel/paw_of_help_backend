import logging
import time

from alembic import command
from alembic.config import Config
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError

from app.core.config import settings
from app.db.base import Base
from app.db.migrate import ensure_postgres_schema, ensure_sqlite_schema
from app.db.session import SessionLocal
from app.modules.account.repository import AccountRepository

logger = logging.getLogger(__name__)

_DB_RETRY_ATTEMPTS = 30
_DB_RETRY_DELAY_SEC = 2


def _alembic_config() -> Config:
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", settings.database_url)
    return cfg


def _is_db_unreachable(exc: BaseException) -> bool:
    if isinstance(exc, OperationalError):
        return True
    msg = str(exc).lower()
    return any(
        token in msg
        for token in (
            "connection refused",
            "could not connect",
            "connection timed out",
            "timeout expired",
            "server closed the connection",
            "database system is starting up",
        )
    )


def run_migrations() -> None:
    cfg = _alembic_config()
    last_err: Exception | None = None
    for attempt in range(1, _DB_RETRY_ATTEMPTS + 1):
        try:
            command.upgrade(cfg, "head")
            return
        except Exception as exc:
            last_err = exc
            if not _is_db_unreachable(exc) or attempt == _DB_RETRY_ATTEMPTS:
                raise
            logger.warning(
                "Database not ready (attempt %s/%s): %s",
                attempt,
                _DB_RETRY_ATTEMPTS,
                exc,
            )
            time.sleep(_DB_RETRY_DELAY_SEC)
    if last_err is not None:
        raise last_err


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
        ensure_postgres_schema(engine)
    _merge_duplicate_org_chat_dialogs()
