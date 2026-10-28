# HAULSIM haulage cases

Nine archived cases cross 283.2 / 354 / 424.8 kWh with 2%, 3% and 4% rolling resistance.

- [Original settings and case metadata](../../data/workspace/New_Afton_Experiments_2026-10-20/run_manifest.json)
- [Native result databases](../../data/workspace/New_Afton_Experiments_2026-10-20/results)
- [Original analysis](../../data/workspace/APCOM_Study_2026-10-22/code/operations.py)
- [Reusable energy and reserve functions](../../src/bev_research/haulage.py)
- [Independent reconstruction](../../tools/audit_physics.py)
- [Recorded case checks](../../audits/physics/independent_case_checks.csv)

Run `bev-reproduce physics --output results/haulage-check-001` from the reproduction package. Reading saved databases does not launch HAULSIM. Native reruns require the licensed application. The external 80% to 20% budget is a postprocessing policy; native runs are not stopped by this cutoff.
