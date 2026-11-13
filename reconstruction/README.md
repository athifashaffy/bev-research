# NumPy reconstruction (28 October 2026)

A separate re-implementation of the study in NumPy and pandas, without
scikit-learn. It is kept for comparison. **It is not the source of the APCOM
2027 paper's numbers.** Those come from
[`reproducibility/experiments/A_live`](../reproducibility/experiments/A_live).

Until 13 November 2026 these folders were at the repository root. They were
moved here unchanged, except that the package was renamed from `bev_research` to
`bev_reconstruction` so that it no longer clashes with `reproducibility/`. Its
tests and script outputs were checked to be identical before and after the move.

| Folder | Contents |
| --- | --- |
| `src/bev_reconstruction/` | thermal model, features, baselines, hand-written ridge and boosting, rules |
| `experiments/` | four entry-point scripts ([README](experiments/README.md)) |
| `code/make_figures.py` | redraws `figures/` from `data/derived` (`--out` writes elsewhere) |
| `code/verify.py` | rechecks headline numbers from `data/derived` |
| `code/fit_thermal_model.py` | byte-identical copy of `reproducibility/data/workspace/APCOM_Coupled_Thermal_2026-10-16/code/fit_model.py`; it runs only from that original folder |
| `data/derived`, `data/manifest` | derived tables and source checksums (committed) |
| `data/raw/` | licence-restricted raw records; not committed (see [data/README.md](data/README.md)) |
| `docs/` | [experiment guide](docs/EXPERIMENT_GUIDE.md) and [figure captions](docs/FIGURE_CAPTIONS.md) |
| `tests/` | pytest suite |

```bash
cd reconstruction
pip install -r requirements.txt pytest
python -m pytest -q tests
python code/verify.py
python experiments/thermal_demand.py --out /tmp/thermal
```
