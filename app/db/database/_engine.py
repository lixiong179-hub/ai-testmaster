from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.pool import QueuePool
import logging

from app.core.config import settings

Base = declarative_base()


def _apply_column_defaults(self, passed_keys):
    for table_column in self.__table__.columns:
        if table_column.default is not None:
            arg = getattr(table_column.default, 'arg', table_column.default)
            if callable(arg):
                continue
            attr_name = table_column.name
            if attr_name not in passed_keys:
                setattr(self, attr_name, arg)


_original_base_init = Base.__init__


def _base_init_with_defaults(self, **kwargs):
    column_names = {c.name for c in self.__table__.columns}
    column_kwargs = {k: v for k, v in kwargs.items() if k in column_names}
    extra_kwargs = {k: v for k, v in kwargs.items() if k not in column_names}

    _original_base_init(self, **column_kwargs)
    _apply_column_defaults(self, set(column_kwargs.keys()))

    for k, v in extra_kwargs.items():
        setattr(self, k, v)


Base.__init__ = _base_init_with_defaults

logger = logging.getLogger(__name__)


def create_database_engine(
    database_url: str,
    pool_size: int = 20,
    pool_timeout: int = 30,
    max_overflow: int = 10,
) -> Engine:
    return create_engine(
        database_url,
        poolclass=QueuePool,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_pre_ping=True,
        pool_recycle=3600,
        pool_timeout=pool_timeout,
        echo=False,
    )


primary_engine = create_database_engine(
    settings.DATABASE_URL,
    pool_size=settings.DB_POOL_SIZE,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    max_overflow=getattr(settings, 'DB_MAX_OVERFLOW', 10),
)

engine = primary_engine

secondary_url = settings.DATABASE_URL_SLAVE if settings.DATABASE_URL_SLAVE else settings.DATABASE_URL
secondary_engine = create_database_engine(
    secondary_url,
    pool_size=settings.DB_POOL_SIZE,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    max_overflow=getattr(settings, 'DB_MAX_OVERFLOW', 10),
)

PrimarySessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=primary_engine)
SecondarySessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=secondary_engine)

primary_scoped_session = scoped_session(PrimarySessionLocal)
secondary_scoped_session = scoped_session(SecondarySessionLocal)
