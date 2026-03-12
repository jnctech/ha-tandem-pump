# ADR-002: Sensor state_class Strategy

**Date:** 2026-03-13
**Status:** Accepted

## Context

Home Assistant sensor entities have a `state_class` attribute that tells HA's recorder how to treat the sensor's values for long-term statistics:

- `MEASUREMENT` — continuous measurement; HA records mean/min/max per hour
- `TOTAL_INCREASING` — monotonically increasing counter (energy meters); HA computes sum, handles resets
- `TOTAL` — accumulating value for the Energy dashboard
- `None` — no statistics recorded

The integration has ~99 sensors across several conceptual categories, each with different data semantics. The upstream (noiwid/HAFamilyLink) set `state_class=TOTAL` on battery and percentage sensors — incorrect usage that produced no usable statistics.

Baseline review finding S-1 (Medium) and S-3 (Medium) identified 8 sensors with incorrect `state_class=MEASUREMENT` that produced meaningless recorder statistics.

## Decision

Apply `state_class` by data category:

| Category | state_class | Rationale |
|---|---|---|
| Continuous readings | `MEASUREMENT` | Glucose level, IOB, basal rate, battery %, reservoir — true measurements that change continuously and whose mean/min/max over time is meaningful |
| Discrete events | `None` | Last bolus, last meal bolus, last cartridge fill — point-in-time snapshots of a single event. Repeating the same value between events produces meaningless statistics |
| Daily-reset accumulators | `None` | Daily insulin total, daily bolus total, daily basal total, daily carbs, daily bolus count — reset to 0 at midnight. HA statistics on reset counters produce nonsensical min/mean/max across day boundaries |
| Metadata / configuration | `None` | Pump serial, software version, alert thresholds, profile names — discrete non-numeric or static values |
| Timestamps | `None` (with `device_class=TIMESTAMP`) | Last upload time, last bolus time — HA handles these via device_class |

## Alternatives Considered

**`TOTAL_INCREASING` for daily accumulators**
Rejected. `TOTAL_INCREASING` is designed for meters that count up indefinitely (utility meters, energy counters). HA compensates for detected resets by assuming the meter rolled over. A daily midnight reset is not a rollover — HA would produce wrong cumulative sums.

**`MEASUREMENT` for all numeric sensors (previous state)**
Rejected (this was the bug fixed in PR #40). Applying MEASUREMENT to discrete events caused HA to record "last bolus = 1.5U" as a repeated mean value for hours between boluses. Applying MEASUREMENT to daily counters caused HA to record daily 0→25→0 saw-tooth patterns as meaningless statistics.

**`TOTAL` for accumulators**
Rejected. `TOTAL` does not produce standard mean/min/max statistics for Statistics Graph cards — it feeds the Energy dashboard specifically.

## Consequences

- 8 sensors corrected in PR #40 (2026-03-13): state_class set to `None`
- Existing HA recorder statistics for those 8 sensors stopped accumulating after PR #40 deploy — historical data is preserved but no new entries
- Historical bolus and carbs data is correctly provided by the explicit LTS imports (ADR-001), not by sensor state_class
- `sensor.py:state_class` property return type is `SensorStateClass | None` to reflect this design
- Open findings S-4 and S-5 (low priority): some threshold sensors may be missing `device_class=BLOOD_GLUCOSE` and `suggested_display_precision`
