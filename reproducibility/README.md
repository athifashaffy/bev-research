# BEV research: reproduce the results

## Run

Use Python 3.12 or later. From this directory:

```text
python -m pip install -e .
bev-reproduce all --output results/check-001
```

Choose a new output directory for each run. Inputs are read only.

## Files

- [Experiment A: forecasting and fitted models](experiments/A)
- [Experiment B: archived laboratory analysis](experiments/B)
- [Haulage accounting](experiments/haulage) and [thermal calculations](experiments/thermal)
- [Source data](data), including [TUM LFP CSV files](data/tum/dataset)
- [Figures](figures), [HAULSIM screenshots](screenshots) and [videos](video)
- [Detailed commands and input layout](docs/RUNNING.md)

These checks reproduce calculations; they do not validate actual Z50 pack
temperature or runaway warning. See [model scope](docs/MODEL_AND_LIMITS.md).
