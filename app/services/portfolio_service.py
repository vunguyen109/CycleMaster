from sqlalchemy.orm import Session
from app.models import models
def get_portfolio(session: Session):
    return session.query(models.Portfolio).all()
