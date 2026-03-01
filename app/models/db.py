from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
from pathlib import Path
from .base import Base
from app.utils.config import settings
from app.migrations.migrate_db import migrate_db


# Ensure database directory exists
def _ensure_db_directory():
    db_path = settings.db_path
    db_dir = os.path.dirname(db_path)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)


_ensure_db_directory()
engine = create_engine(settings.database_url, connect_args={'check_same_thread': False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Initialize database schema and run migrations."""
    Base.metadata.create_all(bind=engine)
    # Run migrations to ensure schema is up to date
    migrate_db(settings.db_path)
