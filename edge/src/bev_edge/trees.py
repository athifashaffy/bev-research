"""Evaluate an exported histogram-gradient-boosting model without scikit-learn.

AI-assisted (Claude, 13 November 2026); see docs/PROVENANCE.md.

The export (reproducibility/tools/build_edge_bundles.py) stores, for every tree,
the split feature, the raw threshold, the missing-value direction, the children
and the leaf values of scikit-learn's fitted predictor nodes. Prediction follows
scikit-learn 1.7.2: start from the baseline, then add each tree's leaf value in
order. A value goes left when it is <= the threshold, or when it is NaN and the
node sends missing values left.
"""
import math

FORMAT = "bev-edge-hgb-v1"


class BoostedTrees:
    def __init__(self, spec):
        if spec.get("format") != FORMAT:
            raise ValueError(f"Unsupported model format: {spec.get('format')!r}")
        self.n_features = int(spec["n_features"])
        self.baseline = float(spec["baseline"])
        self.trees = []
        for t in spec["trees"]:
            columns = (t["feature"], t["threshold"], t["missing_left"], t["left"], t["right"], t["leaf"], t["value"])
            if len({len(c) for c in columns}) != 1:
                raise ValueError("Tree arrays have different lengths")
            self.trees.append(tuple(list(c) for c in columns))

    def predict(self, x):
        if len(x) != self.n_features:
            raise ValueError(f"Expected {self.n_features} inputs, got {len(x)}")
        raw = 0. + self.baseline
        for feature, threshold, missing_left, left, right, leaf, value in self.trees:
            node = 0
            while not leaf[node]:
                v = x[feature[node]]
                go_left = missing_left[node] if math.isnan(v) else v <= threshold[node]
                node = left[node] if go_left else right[node]
            raw += value[node]
        return raw
