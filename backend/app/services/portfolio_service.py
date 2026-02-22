from sqlalchemy.orm import Session
from app.models import models
from app.utils.config import settings


def seed_portfolio(session: Session):
    if session.query(models.Portfolio).count() > 0:
        return
    if not settings.portfolio_symbols:
        return
    symbols = settings.portfolio_symbols.split(',')
    quantities = [float(x) for x in settings.portfolio_quantities.split(',')]
    avg_prices = [float(x) for x in settings.portfolio_avg_price.split(',')]
    for sym, qty, price in zip(symbols, quantities, avg_prices):
        session.add(models.Portfolio(symbol=sym.strip(), quantity=qty, avg_price=price))
    session.commit()


def get_portfolio(session: Session):
    seed_portfolio(session)
    return session.query(models.Portfolio).all()
