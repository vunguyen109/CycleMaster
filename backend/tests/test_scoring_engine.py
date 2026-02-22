import pandas as pd
from app.services.scoring_service import classify_regime


def test_classify_regime_markup():
    data = {
        'date': pd.date_range(end=pd.Timestamp.today().normalize(), periods=120, freq='B'),
        'open': [10 + i * 0.05 for i in range(120)],
        'high': [10 + i * 0.06 for i in range(120)],
        'low': [10 + i * 0.04 for i in range(120)],
        'close': [10 + i * 0.06 for i in range(120)],
        'volume': [100000 + i * 2000 for i in range(120)],
        'ma20': [10 + i * 0.06 for i in range(120)],
        'ma50': [10 + i * 0.05 for i in range(120)],
        'ma100': [10 + i * 0.04 for i in range(120)],
        'rsi': [65 for _ in range(120)],
        'adx': [30 for _ in range(120)],
        'atr': [0.5 for _ in range(120)],
        'volume_ratio': [1.6 for _ in range(120)]
    }
    df = pd.DataFrame(data)
    regime = classify_regime(df)
    assert regime in ['MARKUP', 'ACCUMULATION']
