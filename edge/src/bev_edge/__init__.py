"""Standalone temperature forecaster for on-vehicle use (standard library only).

AI-assisted (Claude, 13 November 2026); see docs/PROVENANCE.md.
"""
from .bundle import Bundle
from .features import FEATURE_NAMES, history_features
from .forecaster import METHODS, Forecaster, SensorBuffer
from .thermal import equivalent_current, thermal_hold

__version__ = "0.1.0"
__all__ = ["Bundle", "FEATURE_NAMES", "Forecaster", "METHODS", "SensorBuffer",
           "equivalent_current", "history_features", "thermal_hold"]
