import numpy as np
import pandas as pd
from sqlalchemy.orm import Session
from app.models import models
from app.ml.hmm_regime import fit_hmm, map_states_to_regimes


def detect_market_regime(session: Session, vnindex_df: pd.DataFrame):
    df = vnindex_df.sort_values('date').copy()
    df['return'] = df['close'].pct_change().fillna(0)
    returns = df['return'].values.reshape(-1, 1)

    if len(returns) < 60:
        regime = 'ACCUMULATION'
        confidence = 50.0
    else:
        model = fit_hmm(returns)
        states = model.predict(returns)
        mapping = map_states_to_regimes(model)
        last_state = states[-1]
        regime = mapping.get(last_state, 'ACCUMULATION')
        post = model.predict_proba(returns)[-1]
        confidence = float(np.max(post) * 100)

    latest_date = df['date'].iloc[-1].date()
    session.add(models.MarketRegime(date=latest_date, regime=regime, confidence=confidence))
    session.commit()
    return regime, confidence, latest_date
