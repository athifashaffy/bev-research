"""Underground BEV thermal warning study.

Simulation-informed thermal demand and a forecasting benchmark for battery
electric haul trucks, built on nine archived HAULSIM configurations, a fitted
A123-equivalent cell thermal model, and published LFP abuse records.

Read this before using anything here. Temperatures produced by this package are
A123-equivalent CELL SURFACE values from a fitted lumped model. They are not
measured, and they are not validated Sandvik Z50 pack, core or hotspot
temperatures. No verified thermal-runaway detection, lead time or field
false-alarm rate is established anywhere in this work.

Layout:

    config      frozen coefficients, screens and the experiment grid
    thermal     the lumped surface model and event replay
    features    causal window features for forecasting
    baselines   persistence, linear trend, held-input physics
    models      ridge and gradient boosted trees, numpy only
    metrics     RMSE, MAE, and the resolution floor they sit against
    rules       the seven frozen warning rules
    datasets    loaders for the committed derived data

Experiment entry points live in ``experiments/`` at the repository root.
"""
from __future__ import annotations

__version__ = "0.2.0"

from . import (baselines, config, datasets, features, metrics, models, rules,
               thermal)

__all__ = ["config", "thermal", "features", "baselines", "models", "metrics",
           "rules", "datasets", "__version__"]
