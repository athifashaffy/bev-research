"""Learned forecasting models, implemented without scikit-learn.

Ridge is solved in closed form. The gradient boosted tree ensemble is written
out here rather than imported, so that the repository reproduces the benchmark
with numpy alone and so that every modelling choice is visible in the source
instead of hidden behind a default.

Being an independent implementation, this will not reproduce scikit-learn's
``HistGradientBoostingRegressor`` numbers exactly. On the archived benchmark the
two agree to within 5 to 19 percent and select the same winner at 2, 5 and
10 minutes. The baselines and ridge, which are deterministic, agree to within
1 to 2 percent.
"""
from __future__ import annotations

import numpy as np

RIDGE_LAMBDAS = (1e-4, 1e-2, 1.0, 10.0, 100.0, 1000.0)


# ------------------------------------------------------------------- ridge
def ridge_fit(design: np.ndarray, target: np.ndarray, lam: float):
    """Closed-form ridge with the intercept left unpenalised.

    Features are standardised on the training split only; the stored mean and
    scale are reapplied at prediction time so that no test statistic leaks into
    the fit.
    """
    mean = design.mean(axis=0)
    scale = design.std(axis=0)
    scale = np.where(scale < 1e-12, 1.0, scale)
    z = np.column_stack([(design - mean) / scale, np.ones(len(design))])
    gram = z.T @ z
    penalty = lam * np.eye(gram.shape[0])
    penalty[-1, -1] = 0.0                      # never penalise the intercept
    weights = np.linalg.solve(gram + penalty, z.T @ target)
    return mean, scale, weights


def ridge_predict(model, design: np.ndarray) -> np.ndarray:
    mean, scale, weights = model
    z = np.column_stack([(design - mean) / scale, np.ones(len(design))])
    return z @ weights


# -------------------------------------------------- gradient boosted trees
class _Node:
    __slots__ = ("feature", "threshold", "left", "right", "is_leaf", "value")

    def __init__(self):
        self.is_leaf = True
        self.value = 0.0


def _best_split(design, grad, rows, n_thresholds):
    """Variance-reduction split search over quantile candidate thresholds."""
    total, count = grad[rows].sum(), len(rows)
    baseline = -(total * total) / count
    best = None
    for feature in range(design.shape[1]):
        values = design[rows, feature]
        candidates = np.unique(np.quantile(
            values, np.linspace(0.05, 0.95, n_thresholds)))
        order = np.argsort(values, kind="stable")
        sorted_v, sorted_g = values[order], grad[rows][order]
        cumulative = np.cumsum(sorted_g)
        positions = np.searchsorted(sorted_v, candidates, side="right")
        positions = positions[(positions > 0) & (positions < count)]
        if positions.size == 0:
            continue
        left_sum = cumulative[positions - 1]
        left_count = positions.astype(float)
        right_sum = total - left_sum
        right_count = count - left_count
        score = -(left_sum ** 2) / left_count - (right_sum ** 2) / right_count
        k = int(np.argmin(score))
        if score[k] < baseline - 1e-18 and (best is None or score[k] < best[0]):
            best = (score[k], feature, sorted_v[positions[k] - 1])
    return best


def _grow(design, grad, rows, depth, max_depth, min_leaf, n_thresholds):
    node = _Node()
    node.value = grad[rows].mean()
    if depth >= max_depth or len(rows) < 2 * min_leaf:
        return node
    split = _best_split(design, grad, rows, n_thresholds)
    if split is None:
        return node
    _, feature, threshold = split
    mask = design[rows, feature] <= threshold
    left_rows, right_rows = rows[mask], rows[~mask]
    if len(left_rows) < min_leaf or len(right_rows) < min_leaf:
        return node
    node.is_leaf = False
    node.feature, node.threshold = feature, threshold
    node.left = _grow(design, grad, left_rows, depth + 1, max_depth,
                      min_leaf, n_thresholds)
    node.right = _grow(design, grad, right_rows, depth + 1, max_depth,
                       min_leaf, n_thresholds)
    return node


def _apply(node, design: np.ndarray) -> np.ndarray:
    out = np.empty(len(design))
    stack = [(node, np.arange(len(design)))]
    while stack:
        current, rows = stack.pop()
        if current.is_leaf:
            out[rows] = current.value
            continue
        mask = design[rows, current.feature] <= current.threshold
        stack.append((current.left, rows[mask]))
        stack.append((current.right, rows[~mask]))
    return out


def gbt_fit(design: np.ndarray, target: np.ndarray, rounds: int = 150,
            learning_rate: float = 0.08, max_depth: int = 3,
            min_leaf: int = 40, n_thresholds: int = 24):
    """Least-squares gradient boosting. Residuals are the gradients."""
    base = float(target.mean())
    prediction = np.full(len(target), base)
    trees = []
    rows = np.arange(len(design))
    for _ in range(rounds):
        residual = target - prediction
        tree = _grow(design, residual, rows, 0, max_depth, min_leaf,
                     n_thresholds)
        prediction = prediction + learning_rate * _apply(tree, design)
        trees.append(tree)
    return base, learning_rate, trees


def gbt_predict(model, design: np.ndarray) -> np.ndarray:
    base, learning_rate, trees = model
    out = np.full(len(design), base)
    for tree in trees:
        out += learning_rate * _apply(tree, design)
    return out


def select_lambda(train_x, train_y, dev_x, dev_y,
                  lambdas=RIDGE_LAMBDAS) -> float:
    """Pick the ridge penalty on a development split, never on the test fold."""
    from .metrics import rmse
    best_lam, best_err = None, np.inf
    for lam in lambdas:
        err = rmse(ridge_predict(ridge_fit(train_x, train_y, lam), dev_x),
                   dev_y)
        if err < best_err:
            best_lam, best_err = lam, err
    return best_lam
