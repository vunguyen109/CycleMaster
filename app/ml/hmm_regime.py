import numpy as np
from hmmlearn.hmm import GaussianHMM


def _standardize_features(X: np.ndarray) -> np.ndarray:
    X = np.asarray(X, dtype=float)
    X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)
    mean = X.mean(axis=0)
    std = X.std(axis=0, ddof=1)
    std[std == 0] = 1.0
    return (X - mean) / std


def fit_hmm(returns: np.ndarray, n_states: int = 4):
    X = _standardize_features(returns)
    model_kwargs = dict(n_components=n_states, covariance_type='diag', n_iter=200, random_state=42)
    try:
        model = GaussianHMM(**model_kwargs, min_covar=1e-5)
    except TypeError:
        model = GaussianHMM(**model_kwargs)
        rng = np.random.default_rng(42)
        X = X + rng.normal(0.0, 1e-6, size=X.shape)
    model.fit(X)
    return model


def map_states_to_regimes(model: GaussianHMM):
    means = model.means_[:, 0]
    order = np.argsort(means)
    regimes = ['MARKDOWN', 'DISTRIBUTION', 'ACCUMULATION', 'MARKUP']
    mapping = {}
    for idx, state in enumerate(order):
        mapping[state] = regimes[idx]
    return mapping
