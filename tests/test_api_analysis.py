from fastapi.testclient import TestClient

from app.main import app
from app.api.routes import ensure_latest_data


def test_analysis_endpoint_returns_list():
    # ensure there is some data in the database; may trigger a scan if empty
    ensure_latest_data()
    client = TestClient(app)

    response = client.get('/analysis/latest')
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    # every item should at least have a symbol and score and trade info
    if data:
        item = data[0]
        assert 'symbol' in item
        assert 'score' in item
        assert 'entry' in item and 'stop' in item and 'target' in item and 'rr' in item
        assert item['entry'] is not None and item['entry'] > 0
        assert item['stop'] is not None and item['stop'] > 0
        assert item['target'] is not None and item['target'] > 0
        # rr should vary across list
        rr_values = [it.get('rr') for it in data if it.get('rr') is not None]
        if len(rr_values) > 1:
            assert any(rr != rr_values[0] for rr in rr_values[1:])

    # also check top_stocks endpoint returns sorted by setup_quality descending
    response2 = client.get('/stocks/top')
    assert response2.status_code == 200
    list2 = response2.json()
    if len(list2) >= 2:
        quals = [it.get('setup_quality') or 0 for it in list2]
        assert quals == sorted(quals, reverse=True)


def test_portfolio_pricing_and_pnl():
    # ensure clean test row
    from app.models.db import SessionLocal
    from app.models import models
    from datetime import date
    session = SessionLocal()
    session.query(models.Portfolio).filter_by(symbol='TEST').delete()
    session.query(models.OHLCV).filter_by(symbol='TEST').delete()
    session.add(models.Portfolio(symbol='TEST', avg_price=1000.0, quantity=2))
    session.add(models.OHLCV(symbol='TEST', date=date.today(), open=1.5, high=1.5, low=1.5, close=1.5, volume=100))
    session.commit()
    session.close()

    client = TestClient(app)
    res = client.get('/portfolio')
    assert res.status_code == 200
    items = res.json()
    t = next((i for i in items if i['symbol'] == 'TEST'), None)
    assert t is not None
    # close in OHLCV was 1.5 (thousands) -> should be converted to 1500
    assert t['last_close'] == 1500
    # pnl = (1500 - 1000) * 2 = 1000
    assert t['pnl_vnd'] == 1000

