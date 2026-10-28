# Model and evidence boundaries

This is technical documentation for auditing existing calculations. Source
reproduction, model assumptions and physical validation are separate questions.

## Haulage inputs and accounting

Nine archived HAULSIM configurations cross nominal energy of 283.2, 354 and
424.8 kWh with assumed uniform rolling resistance of 2%, 3% and 4%. Each native
archive contains a 120-minute run with one replication. Route aggregates are
informed by public operator material; the detailed alignment and several
operating controls are assumptions.

Nominal energy, battery mass, vehicle tare and available power co-vary. These
cases do not isolate the effect of battery energy capacity. The largest
configuration retains a 391 kW native wheel-power cap and a 480 kW electrical
curve, despite a 576 kW nominal rating in the experiment manifest.

The audit interprets native event duration as minutes and battery consumption
as kWh. Event-average power is `60 * energy_kWh / duration_min`. Native battery
energy already reflects the imposed efficiency and auxiliary-power curve;
postprocessing does not apply those losses again. Work/energy consistency is a
numerical check rather than an independent vendor definition of export units.

Native `EnergyLevel` in these archives omits stationary consumption, while the
event consumption ledger includes it. Reserve results therefore use an external
all-state integral. The assumed budget is `0.60 * nominal_energy`, representing
an 80% to 20% nominal-energy policy. The final event is clipped at its average
power; deliveries are credited only after completed unloading. This is a
postprocessed policy, not a native enforced stop or measured electrochemical
state of charge. Charging, swapping and regenerative braking are disabled.

Recurring cycle energy is computed between completed unloading endpoints,
excluding startup and the unfinished tail. Dividing whole-run energy by completed
deliveries gives a different quantity. One recurring cycle falls inside the
common 68.03897-minute comparison window for each case. Repeated cycles are not
independent experimental replications.

## Reference-cell thermal calculation

The current mapping is:

```text
I_eq = Q_ref * P / E_nom
Q_ref = 2.5 Ah; P in kW; E_nom in kWh; I_eq in A
```

`kW/kWh` has units `h^-1`, so multiplying by `Ah` gives amperes without another
factor of 3600. This is an assumed equal-power/nominal-energy reference-cell
loading. It does not identify Z50 pack current or actual current distribution.
For an ideal homogeneous pack using the reference cells and uniform sharing,
`I_eq = I_cell * V/V_nom`. Interpreting it as actual cell current therefore
requires additional voltage and cell assumptions. The actual cell arrangement,
current sharing and pack thermal design are not established here.

The reduced model is:

```text
dT_s/dt = g*a*I_eq^2 - b*(T_s - T_a)
a = 4.344635339312832e-5 K/(A^2 s)
b = 0.002655462788692412 s^-1
```

The fitted ratios are `a = R_eff/C_eff` and `b = UA_eff/C_eff`. Separate
resistance, heat capacity and cooling conductance are not uniquely identified:
scaling all three by the same positive factor leaves both ratios unchanged.
The frozen ratios come from one published A123 cell pulse record. Other records
from that same cell provide comparison residuals, rather than independent-cell
or truck validation.

For constant event-average current and air temperature, the code uses the exact
exponential solution of this equation. Its equilibrium rise is `g*a*I_eq^2/b`
and its time constant is `1/b`, approximately 376.58 seconds. A one-second output
grid adds samples, not additional workload information.

Nominal air and initial temperature both equal 25 C and `g = 1`. The nominal
common-window peak rises are approximately 0.043 to 0.093 C. These are generated
reference-cell surface temperatures. Same-cell comparison-record RMSE values of
approximately 0.109 and 0.117 C are error scales, not confidence limits or truck
error bounds. Additional pack-transfer uncertainty is unquantified.

Sensitivity multipliers for `a`, `b` and `g` are assumed scenarios. Because `a`
and `g` enter as a product, 729 assignments reduce to 405 effective absolute-
temperature input combinations. They are not independent physical experiments
or statistical prediction intervals. Ambient changes translate the curves when
the initial temperature equals air and coefficients remain constant; they do
not establish a mine-ventilation response.

The calculation excludes internal gradients, hotspots, reversible reaction heat,
temperature-dependent resistance, cooling control and abnormal reaction heat.
Event-average current squared does not recover within-event mean-square current
or heat timing. Neither a numerical match nor a sensitivity envelope establishes
pack safety, a cooling specification or an operating-temperature limit.

## Forecasting evidence

Forecast targets are generated nominal temperatures from the same thermal
calculation. The saved benchmark uses horizons of 60, 120, 300 and 600 seconds
and configuration holdouts. Configurations share route structure, thermal
coefficients and constant ambient temperature. Forecast origins overlap.

The ML audit reconciles saved predictions, targets and scores. Original fitted
models existed in memory and were not serialized. These checks do not replay
saved fitted models or supply an independent physical target. Small forecast
errors measure agreement with the deterministic generator; they are not
measurement accuracy on a mine vehicle.

Full raw TUM CSV files are kept separately under `data/tum/`. They are not inputs
to the current forecasts, and no current command treats them as validation data
or trains on them.

## Reproduction boundary

Hash verification establishes file identity. Reconstructed energy and thermal
values establish computational agreement. Neither establishes surveyed route
accuracy, calibrated vehicle dynamics, identified pack physics or measured
temperature accuracy. Inspect the source classifications and audit outputs
alongside the hashes when assessing evidence.

The archive audits and supporting plots do not require HAULSIM. Rerunning the
native simulation requires a HAULSIM license and its application environment.
