# Data types and units

| Source | Time | Quantity | Interpretation |
| --- | --- | --- | --- |
| Native HAULSIM state ledger | minutes | kWh per state | Original simulation output |
| Operations comparison | minutes | kWh, tonnes, completed unloads | External all-state accounting, not native reserve enforcement |
| Nominal thermal traces | seconds | degrees C, equivalent A, kW | Generated A123-equivalent surface response |
| Frozen cell model | seconds | a in K/(A² s), b in s⁻¹ | Fitted coefficient ratios, not separately identified pack parameters |
| Forecast predictions | seconds | degrees C | Generated target and held-out model prediction |
| Pooled forecast metrics | horizon seconds | RMSE/MAE in degrees C | Errors against the generated target |
| TUM original measurement exports | original seconds | degrees C or volts | Published module measurements with original separate clocks |

The paper figure uses target time for forecasts: an estimate displayed at minute
30 for a ten-minute horizon was issued at minute 20. The plot subtracts 25 degrees C
only to show rise; original stored temperatures are unchanged. TUM previews
contain only the first 200 source rows and are not analysis inputs.
