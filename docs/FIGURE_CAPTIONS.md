# Figure captions

Captions for use in the manuscript. Conference and journal style places the
caption **below** the figure and does not repeat it as a title inside the image,
so when these figures are placed in the paper the embedded titles should be
removed. `code/make_figures.py` can emit title-free versions by setting
`SHOW_TITLES = False` at the top of the file.

Every caption states the evidence domain, because the single most common way to
misread this study is to take a modelled surrogate temperature for a measured
pack temperature.

---

**Figure 1.** Analysis pipeline from archived HAULSIM haulage simulation to
warning-rule evaluation. Blue stages are simulated haulage, orange stages are
synthetic temperature derived from an assumed equivalent current, and green
stages are measured laboratory records. No temperature exists before the
equivalent-current step.

**Figure 2.** The four evidence domains used in this study and the inferences
each one does not support. Sample counts are given for each domain. The TUM
channels are six dependent thermocouples on a single module experiment, not six
independent experiments.

**Figure 3.** Mean power and energy per recurring cycle for the nine simulated
configurations, grouped by nominal pack capacity. The dashed line marks the
480 kW continuous rating of the Sandvik Z50. Capacity, vehicle mass and
available power vary together across the archived cases, so these compare whole
vehicle configurations and do not isolate a pure capacity effect.

**Figure 4.** Reserve-limited operating window by configuration, with the number
of complete recurring cycles achieved. External analysis stops at an energy
budget of 60 percent of nominal capacity, representing 80 to 20 percent state of
charge. The underlying simulation may continue past this point.

**Figure 5.** Worked thermal example for case C100_RR03 (354 kWh nominal,
3 percent rolling resistance). (a) The full reserve-limited window. (b) One
loaded-haul event, native event Id 44 in `HS_EquipmentState`, showing the saved
trace samples against the closed-form solution of
dT/dt = a·I² − b·(T − T_air) at constant current, with the time constant
τ = 1/b = 376.58 s and the equilibrium rise a·I²/b. The event terminates well
before equilibrium. Temperatures are A123-equivalent cell surface values and are
not measured pack temperatures.

**Figure 6.** Peak A123-equivalent surface temperature for the nine
configurations, shown (a) against the declared 60 °C study screen and the 55 °C
datasheet operating limit, and (b) magnified approximately one thousandfold.
The margin to the 60 °C screen is 34.907 to 34.957 °C across all nine cases, a
spread of 0.05 °C. The ordering visible in panel (b) is internally consistent,
larger packs running cooler and higher rolling resistance running hotter, but
its magnitude lies below the 0.109 to 0.117 °C residual error of the underlying
measured-cell fit.

**Figure 7.** Pooled forecast RMSE by method and horizon on the nine synthetic
configurations, from nine leave-one-configuration-out holdouts. The shaded band
marks the held-out residual error of the measured-cell thermal fit, 0.109 to
0.117 °C. The entire benchmark lies below this band, so differences between
methods are not physically resolvable. At the ten-minute horizon both the trend
and the held-input physics baselines exceed persistence.

**Figure 8.** Pooled RMSE and MAE by forecast horizon for the same benchmark.
Histogram gradient boosting leads on both measures at 2, 5 and 10 minutes. At
1 minute it leads on RMSE but the held-input physics baseline leads on MAE
(4.317 × 10⁻⁴ against 6.706 × 10⁻⁴ °C), which is why the result is stated for
2, 5 and 10 minutes only.

**Figure 9.** Time of first response of the seven frozen warning rules on
published laboratory records: 27 Sheffield LFP cell records across 8 date
groups, and 6 temperature channels from one TUM module experiment. Bars span the
minimum to maximum first-response time across records, with the median marked.
These are responses to recorded heating, not verified thermal-runaway
detections. No independent, temperature-free onset reference with a bounded
sensor-clock uncertainty is available in either archive, so lead time, missed
detections and field false-alarm rate are not reported.

**Figure 10.** Frozen-rule screening of modelled normal-operation trajectories.
None of the seven rules produced a debounced alarm on any of the nine nominal or
729 assumed-variant trajectories. The denominator is modelled scenarios and
samples, not field exposure, and the nine nominal settings are a subset of the
729 rather than nine additional experiments.

---

## Table captions

**Table 2.** Haulage demand and A123-equivalent surface response for the nine
simulated configurations. Temperature columns are modelled surrogate values, not
measured or validated pack temperatures; the margin is to the declared 60 °C
study screen.

**Table 4.** Pooled forecast error across nine leave-one-configuration-out
holdouts on the synthetic configurations. These measure agreement with the
study's own thermal generator and are not a physical validation.

**Table 5.** Response of the seven frozen warning rules on published laboratory
records. Lead time, missed detections and field false-alarm rate are reported as
unavailable; the per-record reason is given in the event register.
