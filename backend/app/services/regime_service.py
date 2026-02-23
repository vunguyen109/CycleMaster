import numpy as np
import pandas as pd
from sqlalchemy.orm import Session
from app.models import models
from app.ml.hmm_regime import fit_hmm, map_states_to_regimes


def detect_market_regime(session: Session, vnindex_df: pd.DataFrame):
    df = vnindex_df.sort_values('date').copy()
    df['return'] = df['close'].pct_change().fillna(0)
    df['vol_20'] = df['return'].rolling(20).std().fillna(0)
    df['ma20'] = df['close'].rolling(20).mean()
    df['ma20_slope'] = df['ma20'].diff(5).fillna(0)
    features = df[['return', 'vol_20', 'ma20_slope']].fillna(0).values

    if len(features) < 60:
        regime = 'NEUTRAL'
        confidence = 50.0
    else:
        model = fit_hmm(features)
        states = model.predict(features)
        mapping = map_states_to_regimes(model)
        last_state = states[-5:]
        last_state = int(np.bincount(last_state).argmax())
        regime = mapping.get(last_state, 'ACCUMULATION')
        post = model.predict_proba(features)[-1]
        confidence = float(np.max(post) * 100)
        if confidence < 55:
            regime = 'NEUTRAL'

    latest_date = df['date'].iloc[-1].date()
    session.add(models.MarketRegime(date=latest_date, regime=regime, confidence=confidence))
    session.commit()
    return regime, confidence, latest_date
