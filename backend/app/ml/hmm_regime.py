import numpy as np
from hmmlearn.hmm import GaussianHMM


def fit_hmm(returns: np.ndarray, n_states: int = 4):
    model = GaussianHMM(n_components=n_states, covariance_type='full', n_iter=200)
    model.fit(returns)
    return model


def map_states_to_regimes(model: GaussianHMM):
    means = model.means_[:, 0]
    order = np.argsort(means)
    regimes = ['MARKDOWN', 'DISTRIBUTION', 'ACCUMULATION', 'MARKUP']
    mapping = {}
    for idx, state in enumerate(order):
        mapping[state] = regimes[idx]
    return mapping
