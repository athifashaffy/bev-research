# BEV research: reproduce the results

## Run

Use Python 3.12 or later. From this directory:

```text
python -m pip install -e .
bev-reproduce all --output results/check-001
```

Choose a new output directory for each run. Inputs are read only.

## Files

- [Experiment index](experiments/README.md); **[A_live](experiments/A_live) produced the paper's Table 2**
- [Experiment A: forecasting and fitted models](experiments/A)
- [Experiment B: archived laboratory analysis](experiments/B)
- [Haulage accounting](experiments/haulage) and [thermal calculations](experiments/thermal)
- [Source data](data), including [TUM LFP CSV files](data/tum/dataset)
- [Figures](figures), [HAULSIM screenshots](screenshots) and [videos](video)
- [Detailed commands and input layout](docs/RUNNING.md)
- `FILE_MANIFEST.csv`: SHA-256 snapshot of this folder on 28 October 2026 (files changed or added later are not listed)
- `tools/build_edge_bundles.py`: builds the model bundles for the [edge forecaster](../edge)

These checks reproduce calculations; they do not validate actual Z50 pack
temperature or runaway warning. See [model scope](docs/MODEL_AND_LIMITS.md).
