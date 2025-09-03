import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from ..config.config import ConfigManager
from ..config.distribution import get_distribution_manager
from ..database.models import Base
from contextlib import contextmanager

# Lazy initialization - don't create config/engine at import time
_config = None
_engine = None
_Session = None


def _ensure_initialized():
    """Ensure database connection is initialized with current environment."""
    global _config, _engine, _Session

    if _config is None or _engine is None:
        _config = ConfigManager().load_config()

        # Configure SQLite for better concurrency if it's SQLite
        if _config.database.url.startswith("sqlite"):
            _engine = create_engine(
                _config.database.url,
                echo=False,
                pool_timeout=30,
                pool_recycle=-1,
                pool_pre_ping=True,
                connect_args={
                    "timeout": 60,
                    "check_same_thread": False,
                    "isolation_level": None,  # Enable autocommit mode
                },
            )
        else:
            _engine = create_engine(_config.database.url, echo=False)

        _Session = sessionmaker(bind=_engine)


def get_config():
    """Get the current configuration."""
    _ensure_initialized()
    return _config


# Backward compatibility - create a config object that auto-initializes
class _ConfigProxy:
    def __getattr__(self, name):
        return getattr(get_config(), name)


config = _ConfigProxy()


def init_db():
    """Initialize database tables."""
    _ensure_initialized()

    # Ensure database directory exists using distribution manager
    dist_manager = get_distribution_manager()
    db_path = dist_manager.get_database_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    Base.metadata.create_all(_engine)


def get_db():
    """Get a database session."""
    _ensure_initialized()
    return _Session()


@contextmanager
def db_session():
    """Provide a transactional scope around a series of operations."""
    session = get_db()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        raise
    finally:
        session.close()
