"""Database utility functions for common patterns."""

import time
from contextlib import contextmanager
from typing import Any, Callable, List, Optional, Type, TypeVar
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, OperationalError

from ..core import db_session, get_db

T = TypeVar("T")


@contextmanager
def safe_db_operation(max_retries: int = 3, retry_delay: float = 0.5):
    """Context manager for safe database operations with retry logic."""
    last_exception = None

    for attempt in range(max_retries):
        try:
            with db_session() as session:
                yield session
                return
        except (OperationalError, IntegrityError) as e:
            last_exception = e
            if attempt < max_retries - 1 and (
                "database is locked" in str(e).lower() or "locked" in str(e).lower()
            ):
                time.sleep(retry_delay * (1.5**attempt))
                continue
            else:
                break
        except Exception as e:
            last_exception = e
            break

    if last_exception:
        raise last_exception


def get_or_create(
    session: Session, model: Type[T], defaults: dict = None, **kwargs
) -> tuple[T, bool]:
    """Get an existing record or create a new one."""
    instance = session.query(model).filter_by(**kwargs).first()
    if instance:
        return instance, False
    else:
        params = dict((k, v) for k, v in kwargs.items())
        params.update(defaults or {})
        instance = model(**params)
        session.add(instance)
        return instance, True


def bulk_insert_or_update(
    session: Session,
    model: Type[T],
    records: List[dict],
    unique_fields: List[str],
    batch_size: int = 100,
) -> dict:
    """Bulk insert or update records with deduplication."""
    results = {"inserted": 0, "updated": 0, "errors": 0, "duplicates": 0}

    for i in range(0, len(records), batch_size):
        batch = records[i : i + batch_size]

        for record in batch:
            try:
                # Check if record exists based on unique fields
                filter_kwargs = {
                    field: record[field] for field in unique_fields if field in record
                }
                existing = session.query(model).filter_by(**filter_kwargs).first()

                if existing:
                    # Update existing record
                    for key, value in record.items():
                        if hasattr(existing, key):
                            setattr(existing, key, value)
                    results["updated"] += 1
                else:
                    # Create new record
                    new_record = model(**record)
                    session.add(new_record)
                    results["inserted"] += 1

            except IntegrityError:
                session.rollback()
                results["duplicates"] += 1
            except Exception as e:
                session.rollback()
                results["errors"] += 1
                import logging

                logging.error(f"Error processing record: {str(e)}")

    return results


def safe_query(
    session: Session, query_func: Callable, default_return: Any = None
) -> Any:
    """Safely execute a database query with error handling."""
    try:
        return query_func(session)
    except Exception as e:
        import logging

        logging.error(f"Database query error: {str(e)}")
        return default_return


def paginate_query(query, page: int = 1, per_page: int = 50) -> dict:
    """Paginate a SQLAlchemy query and return results with metadata."""
    total = query.count()
    items = query.offset((page - 1) * per_page).limit(per_page).all()

    return {
        "items": items,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page,
        "has_prev": page > 1,
        "has_next": page * per_page < total,
    }


def execute_with_retry(
    operation: Callable, max_retries: int = 3, retry_delay: float = 0.5
) -> Any:
    """Execute a database operation with retry logic for transient failures."""
    last_exception = None

    for attempt in range(max_retries):
        try:
            return operation()
        except (OperationalError, IntegrityError) as e:
            last_exception = e
            if attempt < max_retries - 1 and (
                "database is locked" in str(e).lower() or "locked" in str(e).lower()
            ):
                time.sleep(retry_delay * (1.5**attempt))
                continue
            else:
                break
        except Exception as e:
            last_exception = e
            break

    if last_exception:
        raise last_exception


class DatabaseManager:
    """Helper class for common database operations."""

    def __init__(self):
        self.error_handler = None

    def set_error_handler(self, error_handler):
        """Set error handler for logging."""
        self.error_handler = error_handler

    def _log_error(self, message: str, exception: Exception = None):
        """Log error using error handler or fallback to logging."""
        if self.error_handler:
            self.error_handler.log_error(message, exception)
        else:
            import logging

            logging.error(f"DatabaseManager: {message}")

    def safe_get_by_id(
        self, session: Session, model: Type[T], record_id: int
    ) -> Optional[T]:
        """Safely get a record by ID with error handling."""
        try:
            return session.query(model).filter_by(id=record_id).first()
        except Exception as e:
            self._log_error(f"Error fetching {model.__name__} with ID {record_id}", e)
            return None

    def safe_create(self, session: Session, model: Type[T], **kwargs) -> Optional[T]:
        """Safely create a new record with error handling."""
        try:
            record = model(**kwargs)
            session.add(record)
            session.flush()  # Get ID without committing
            return record
        except Exception as e:
            session.rollback()
            self._log_error(f"Error creating {model.__name__}", e)
            return None

    def safe_update(self, session: Session, record: T, **kwargs) -> bool:
        """Safely update a record with error handling."""
        try:
            for key, value in kwargs.items():
                if hasattr(record, key):
                    setattr(record, key, value)
            session.flush()
            return True
        except Exception as e:
            session.rollback()
            self._log_error(f"Error updating {type(record).__name__}", e)
            return False

    def safe_delete(self, session: Session, record: T) -> bool:
        """Safely delete a record with error handling."""
        try:
            session.delete(record)
            session.flush()
            return True
        except Exception as e:
            session.rollback()
            self._log_error(f"Error deleting {type(record).__name__}", e)
            return False
