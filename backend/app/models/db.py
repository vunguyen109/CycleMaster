from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .base import Base
from app.utils.config import settings


engine = create_engine(settings.database_url, connect_args={'check_same_thread': False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    Base.metadata.create_all(bind=engine)
