from sqlalchemy.orm import Session
from app.models import models


def get_distribution_alerts(session: Session):
    alerts = []
    latest_scores = session.query(models.StockScore).order_by(models.StockScore.date.desc()).all()
    seen = set()
    for score in latest_scores:
        if score.stock_id in seen:
            continue
        seen.add(score.stock_id)
        if score.regime == 'DISTRIBUTION':
            alerts.append(score)
    return alerts
