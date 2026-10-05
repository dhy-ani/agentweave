"""
Schema bootstrap: create missing tables, then add columns introduced after a
table was first created (create_all never alters existing tables). This is a
deliberately tiny stand-in for a migration tool while the schema only grows
by nullable columns.
"""
from __future__ import annotations

import logging

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from . import models  # noqa: F401  (registers tables on Base.metadata)
from .database import Base

logger = logging.getLogger(__name__)


def init_schema(engine: Engine) -> None:
    Base.metadata.create_all(bind=engine)

    inspector = inspect(engine)
    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            existing = {col["name"] for col in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name in existing:
                    continue
                if not column.nullable:
                    raise RuntimeError(f"Cannot auto-add NOT NULL column {table.name}.{column.name}")
                col_type = column.type.compile(dialect=engine.dialect)
                conn.execute(text(f'ALTER TABLE {table.name} ADD COLUMN "{column.name}" {col_type}'))
                logger.info("Added column %s.%s (%s)", table.name, column.name, col_type)
