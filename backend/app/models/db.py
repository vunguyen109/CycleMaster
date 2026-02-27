from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .base import Base
from app.utils.config import settings
from app.migrations.migrate_db import migrate_db


engine = create_engine(settings.database_url, connect_args={'check_same_thread': False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    Base.metadata.create_all(bind=engine)
    # Run migrations to ensure schema is up to date
    db_path = settings.database_url.replace('sqlite:///', '') if 'sqlite:///' in settings.database_url else './data/cyclemaster.db'
    migrate_db(db_path)
