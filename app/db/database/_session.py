from contextlib import contextmanager
from typing import Generator
import logging

from sqlalchemy.orm import Session

from app.db.database._engine import (
    PrimarySessionLocal,
    SecondarySessionLocal,
)

logger = logging.getLogger(__name__)


def get_db() -> Generator:
    db = PrimarySessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f"数据库会话错误: {e}")
        db.rollback()
        raise
    finally:
        db.close()


def get_read_db() -> Generator:
    db = SecondarySessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f"数据库会话错误: {e}")
        db.rollback()
        raise
    finally:
        db.close()


@contextmanager
def get_db_context() -> Generator[Session, None, None]:
    db = PrimarySessionLocal()
    try:
        yield db
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"数据库操作错误: {e}")
        raise
    finally:
        db.close()


@contextmanager
def get_read_db_context() -> Generator[Session, None, None]:
    db = SecondarySessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f"数据库读取错误: {e}")
        raise
    finally:
        db.close()
