# bev-edge: on-vehicle temperature forecaster

A small, standalone version of the paper's forecaster (Experiment A_live) for
running next to the vehicle on a small Linux computer. It reads one sensor
reading per second and, every 10 seconds, forecasts the battery temperature
1, 2, 5, 10 and 30 minutes ahead.

- **No dependencies.** Plain Python 3.9 or newer. No NumPy, no scikit-learn, no
  pickle files. The HGB models are stored as JSON lists of decision trees.
- **Proven identical to the paper's code.** Replaying the saved sensor record of
  configuration C100_RR03 through this package reproduces all 9,008 saved
  forecasts of the Table 2 run exactly (4 methods × 5 horizons, bit for bit).
- **Refuses bad input instead of guessing.** A missing second, repeated time or
  non-finite reading empties the 61-second buffer. Nothing is interpolated or
  filled in; forecasts resume after 61 good consecutive seconds.

> **Important limit.** All models here were trained on *simulated*
> reference-cell temperatures (HAULSIM activity energy → Equation (2) → the
> fitted heat model), with perfect noiseless sensors. They have never seen a
> real truck battery. On a real vehicle they show that the software pipeline
> works. They do not give trustworthy pack temperatures until they are retrained
> and tested on measured data (see [Moving to real data](#moving-to-real-data)).

---

## Quick start (on any computer)

```bash
cd edge
pip install .                        # or skip, and use: PYTHONPATH=src python3 -m bev_edge ...
bev-edge info --bundle bundles/deploy-all9-2026-11-13
bev-edge run  --bundle bundles/deploy-all9-2026-11-13 --capacity-kwh 354 --rr-pct 3 \
              --input examples/C100_RR03/sensor_stream.csv | head -3
python3 -m unittest discover -s tests -v      # 13 tests, about 0.2 s
```

## Input

CSV with a header row, one row per second, oldest first:

| Column | Unit | Meaning |
| --- | --- | --- |
| `time_s` | s | whole-second timestamp; each row must be the previous + 1 |
| `temperature_c` | °C | battery (reference-cell) surface temperature |
| `air_c` | °C | air temperature |
| `equivalent_current_a` | A | current of the 2.5 Ah reference cell, **or** |
| `pack_power_kw` | kW | pack power, converted by Equation (2): I = 2.5 × P ÷ capacity |

`--capacity-kwh` and `--rr-pct` (pack capacity, road rolling resistance) are
model inputs and must be given. Use `--input -` (the default) to read from a
pipe, so a sensor-reading program can feed it live:

```bash
my-sensor-reader | bev-edge run --bundle bundles/deploy-all9-2026-11-13 --capacity-kwh 354 --rr-pct 3
```

## Output

One JSON line per forecast (every 10 s once 61 seconds are buffered):

```json
{"time_s": 60, "temperature_c": 25.000141455691, "bundle": "deploy-all9-2026-11-13",
 "forecasts": [{"horizon_s": 60, "target_time_s": 120, "persistence": 25.000141455691,
   "linear_trend": 25.000283773831, "physics_hold": 25.000348309556802,
   "hist_gradient_boosting": 25.000232136473077}, ...]}
```

`hist_gradient_boosting` is the HGB forecast. The other three are the paper's
baselines: no change, straight-line trend, and the thermal model (Equation (5)
with the current held).

## Model bundles

| Bundle | What it is | Use it for |
| --- | --- | --- |
| `bundles/paper-heldout-C100_RR03/` | The paper's own five HGB models that were trained **without** C100_RR03 (from `reproducibility/results/run-2026-11-13/live`). Converted, not retrained. | Proving the edge code matches the paper (the replay test). |
| `bundles/deploy-all9-2026-11-13/` | **New** models trained on 13 Nov 2026 on all nine configurations with the paper's settings. Not the paper's models, and they have no test score of their own because nothing was held out. | Running on the device. The paper's Table 2 is the evidence for how this method generalises to an unseen configuration. |

Each bundle has a `manifest.json` that records where it came from, the input and
script SHA-256 hashes, the software versions, and the SHA-256 of every model file.
Changed model files are refused when loaded. Bundles are built by
`reproducibility/tools/build_edge_bundles.py`. That tool writes only to new
folders, and checks every exported model against scikit-learn on all training
rows before saving it.

## Layout

```text
edge/
├── src/bev_edge/
│   ├── features.py     20 inputs from the last 61 seconds (copy of A_causal/inputs.py stable_features)
│   ├── thermal.py      Equation (2) and the thermal baseline (Equation (5), current held)
│   ├── trees.py        evaluates exported HGB trees
│   ├── bundle.py       loads a bundle and checks its hashes
│   ├── forecaster.py   SensorBuffer (61 s rolling window) and Forecaster
│   └── cli.py          bev-edge info / run
├── bundles/            model bundles (see above)
├── examples/C100_RR03/ saved sensor record + expected forecasts (replay fixture)
└── tests/test_edge.py
```

## Using it from Python

```python
from bev_edge import Bundle, Forecaster

f = Forecaster(Bundle("bundles/deploy-all9-2026-11-13"), capacity_kwh=354, rr_pct=3)
for t, current_a, temp_c, air_c in sensor_readings():      # your 1 Hz source
    result = f.push(t, current_a, temp_c, air_c)
    if result:
        send(result)                                       # e.g. log, MQTT, display
```

## Moving to real data

When the device and real readings are available:

1. **Record first, forecast later.** Log raw 1 Hz readings unchanged, with the
   sensor clock. Keep the original files and their SHA-256 hashes.
2. **Decide what "current" means.** The models expect a 2.5 Ah reference-cell
   current. With real pack current or power, either convert with Equation (2)
   (an assumption) or retrain on the measured quantity directly.
3. **Retrain and test on held-out real data**, using the same nested
   leave-one-out evaluation as the paper, before trusting any forecast. Build a
   new bundle with a new name. Never overwrite these ones.
4. Sensor noise, delays and missing samples were not part of the simulation.
   Expect the buffer to reset more often on real hardware.

AI assistance: this package and its bundles were written with AI assistance
(Claude, 13 November 2026); see [docs/PROVENANCE.md](../docs/PROVENANCE.md).
