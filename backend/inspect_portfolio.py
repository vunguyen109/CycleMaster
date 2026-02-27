from app.models.db import SessionLocal
from app.models import models

def main():
    session = SessionLocal()
    items = session.query(models.Portfolio).all()
    print('portfolio items:')
    for it in items:
        print(it.symbol, it.avg_price, it.quantity)
        ohlcv = session.query(models.OHLCV).filter_by(symbol=it.symbol).order_by(models.OHLCV.date.desc()).first()
        if ohlcv:
            print(' last close raw', ohlcv.close)
    session.close()

if __name__ == '__main__':
    main()
