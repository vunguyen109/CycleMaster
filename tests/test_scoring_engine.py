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


def test_score_stock_sane_distribution():
    # build a simple increasing price series to ensure breakout >0
    data = {
        'date': pd.date_range(end=pd.Timestamp.today().normalize(), periods=150, freq='B'),
        'open': [10 + i * 0.1 for i in range(150)],
        'high': [10 + i * 0.1 + 0.05 for i in range(150)],
        'low': [10 + i * 0.1 - 0.05 for i in range(150)],
        'close': [10 + i * 0.1 for i in range(150)],
        'volume': [100000 for _ in range(150)],
        'ma20': [10 + i * 0.1 for i in range(150)],
        'ma50': [10 + i * 0.1 for i in range(150)],
        'ma100': [10 + i * 0.1 for i in range(150)],
        'rsi': [50 for _ in range(150)],
        'adx': [25 for _ in range(150)],
        'atr': [0.5 for _ in range(150)],
        'volume_ratio': [1.0 for _ in range(150)]
    }
    df = pd.DataFrame(data)
    vni = df.copy()
    from app.services.scoring_service import score_stock
    # score with dummy session (None should be tolerated if not used)
    score = score_stock(None, 'AAA', df, vni, market_regime='MARKUP')
    assert isinstance(score, dict)
    # core score range
    assert 0.0 <= score['score'] <= 100.0
    # new action field replaces setup_status
    assert score['action'] in ['BUY', 'WATCH', 'AVOID']
    # signal parameters should all be positive numbers
    for key in ('entry', 'stop', 'target', 'rr', 'setup_quality'):
        assert key in score
        assert score[key] is not None
        assert isinstance(score[key], (int, float))
        assert score[key] > 0
    # rr should vary, not constant 1.5
    assert score['rr'] != 1.5


def test_score_stock_nonpositive_close():
    # a close price of zero or negative should cause skip (None returned)
    # reuse previous series from s/sane_distribution test
    df2 = pd.DataFrame({
        'date': pd.date_range(end=pd.Timestamp.today().normalize(), periods=150, freq='B'),
        'open': [10 + i * 0.1 for i in range(150)],
        'high': [10 + i * 0.1 + 0.05 for i in range(150)],
        'low': [10 + i * 0.1 - 0.05 for i in range(150)],
        'close': [10 + i * 0.1 for i in range(150)],
        'volume': [100000 for _ in range(150)],
        'ma20': [10 + i * 0.1 for i in range(150)],
        'ma50': [10 + i * 0.1 for i in range(150)],
        'ma100': [10 + i * 0.1 for i in range(150)],
        'rsi': [50 for _ in range(150)],
        'adx': [25 for _ in range(150)],
        'atr': [0.5 for _ in range(150)],
        'volume_ratio': [1.0 for _ in range(150)]
    })
    vni2 = df2.copy()
    df2.loc[df2.index[-1], 'close'] = 0.0
    score2 = score_stock(None, 'BBB', df2, vni2, market_regime='MARKUP')
    assert score2 is None


def test_validate_signal_output():
    from app.services.scoring_service import validate_signal_output
    good = {
        'score': 50,
        'confidence': 50,
        'entry': 10,
        'stop': 9,
        'target': 12,
        'rr': 3
    }
    ok, reason = validate_signal_output(good)
    assert ok
    assert reason == ''
    bad = {
        'score': None,
        'confidence': 50,
        'entry': 10,
        'stop': 9,
        'target': 12,
        'rr': 3
    }
    ok, reason = validate_signal_output(bad)
    assert not ok
    assert 'invalid_score' in reason
