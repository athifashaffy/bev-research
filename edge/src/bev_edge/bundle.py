"""Load a model bundle: manifest.json plus one exported model per horizon.

AI-assisted (Claude, 13 November 2026); see docs/PROVENANCE.md.

Every model file's SHA-256 is checked against the manifest before use, so a
changed or corrupted file is refused instead of silently forecasting.
"""
import hashlib
import json
from pathlib import Path

from .features import FEATURE_NAMES
from .trees import BoostedTrees

FORMAT = "bev-edge-bundle-v1"


class Bundle:
    def __init__(self, folder):
        self.folder = Path(folder)
        self.manifest = json.loads((self.folder / "manifest.json").read_text(encoding="utf-8"))
        m = self.manifest
        if m.get("format") != FORMAT:
            raise ValueError(f"Unsupported bundle format: {m.get('format')!r}")
        if m["feature_names"] != FEATURE_NAMES:
            raise ValueError("Bundle feature names differ from this forecaster's inputs")
        self.name = m["name"]
        self.kind = m["kind"]
        self.a = float(m["thermal"]["a_K_per_A2_s"])
        self.b = float(m["thermal"]["b_per_s"])
        self.horizons = [int(h) for h in m["horizons_s"]]
        self.models = {}
        for h in self.horizons:
            entry = m["models"][str(h)]
            path = self.folder / entry["file"]
            data = path.read_bytes()
            if hashlib.sha256(data).hexdigest() != entry["sha256"]:
                raise ValueError(f"Model file changed since export: {entry['file']}")
            self.models[h] = BoostedTrees(json.loads(data))

    def describe(self):
        m = self.manifest
        return {"name": self.name, "kind": self.kind, "label": m["label"], "created_utc": m["created_utc"],
                "horizons_s": self.horizons, "trees_per_horizon": {h: len(t.trees) for h, t in self.models.items()}}
