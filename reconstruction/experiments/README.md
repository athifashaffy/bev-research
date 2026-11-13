# Experiments

Run from the repository root:

```text
python experiments/thermal_demand.py
python experiments/experiment_a_forecasting.py
python experiments/experiment_b_warning_rules.py
python experiments/reproduce_thermal_chain.py
```

| Script | Purpose |
| --- | --- |
| `thermal_demand.py` | Nine-case energy, reserve and thermal summaries |
| `experiment_a_forecasting.py` | NumPy forecasting reconstruction |
| `experiment_b_warning_rules.py` | Replay archived rule-response results |
| `reproduce_thermal_chain.py` | Rebuild temperatures from the event ledger |

Outputs go under `results/`. Archived inputs are preserved in `data/derived/`.
The separate [original forecasting implementation](../reproducibility/experiments/A)
uses scikit-learn and saves newly fitted models.

See the [methods, result windows and limitations](../docs/EXPERIMENT_GUIDE.md).
