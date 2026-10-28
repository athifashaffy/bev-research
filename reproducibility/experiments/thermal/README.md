# Reference-cell thermal calculation

- [Thermal model implementation](../../src/bev_research/thermal_model.py)
- [Frozen fitted coefficients](../../data/workspace/APCOM_Coupled_Thermal_2026-10-16/results/frozen_cell_model.json)
- [Original thermal analysis](../../data/workspace/APCOM_Draft_Experiments_2026-10-27/thermal/run_thermal.py)
- [Nominal traces and sensitivity outputs](../../data/workspace/APCOM_Draft_Experiments_2026-10-27/thermal)
- [Equations and units audit](../../audits/physics/equation_audit.csv)

The source model uses a 2.5 Ah reference cell with assumed equivalent current from simulated power/nominal energy. The two fitted ratios do not independently identify resistance, heat capacity or cooling, and do not establish actual Z50 pack temperatures. Numerical reconstruction covers 45,094 samples and 729 parameter assignments. See the model guide for physical limits.
