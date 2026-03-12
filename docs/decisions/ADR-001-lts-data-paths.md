# ADR-001: Long-Term Statistics — Two Data Paths

**Date:** 2026-03-13
**Status:** Accepted

## Context

Home Assistant users expect to chart historical pump data (glucose trends, insulin delivery, basal rates) using the Statistics Graph card. The integration needed a strategy for producing HA long-term statistics from Tandem Source API data.

Two mechanisms exist in HA for recording statistics:

1. **Automatic recorder sampling** — HA's recorder periodically (~5 min) samples the current state of any sensor with `state_class` set. It stores mean/min/max per hour.
2. **Explicit `async_import_statistics()` API** — code can push pre-computed `StatisticData` objects with arbitrary timestamps directly into HA's statistics tables.

The Tandem Source API returns two kinds of data:
- **Current state** — present sensor readings (current glucose, active IOB, battery level)
- **Event history** — a list of timestamped pump events (each bolus delivery, each CGM reading, each basal change)

## Decision

Use **explicit `_import_statistics()` imports** for the 6 LTS types that matter for historical analysis. Do not rely on automatic recorder sampling for event-based or daily-reset data.

The 6 explicitly imported statistic types (`__init__.py:2038-2194`):

| Statistic ID | Data | Source Events |
|---|---|---|
| `sensor.carelink_last_glucose_level_mmol` | CGM glucose (mmol/L) | event 256 |
| `sensor.carelink_active_insulin_iob` | Active insulin (IOB) | events 20, 21 |
| `sensor.carelink_basal_rate` | Basal rate (U/hr) | events 3, 279 |
| `sensor.carelink_meal_carbs` | Meal carbs (g) | event 48 |
| `sensor.carelink_total_bolus` | Completed bolus delivery (U) | events 20/21, completion_status=3 |
| `sensor.carelink_correction_bolus` | Correction bolus (U) | event 280, delivery_status=0 |

Statistics are bucketed hourly (`has_mean=True, has_sum=False`). Timestamps come from actual pump event times, not from when HA polls.

## Alternatives Considered

**1. Rely entirely on `state_class=MEASUREMENT` automatic sampling**
Rejected. HA's recorder samples the sensor's *current* value every ~5 minutes. For event-based data (a bolus that happened at 14:23), the sensor shows that bolus value until the next bolus — so HA would record "1.5U" repeatedly for hours between boluses. Statistics would show meaningless long-duration averages of point-in-time event values. Accuracy degrades with infrequent events.

**2. Use `state_class=TOTAL_INCREASING`**
Rejected for daily-reset counters. HA's `TOTAL_INCREASING` is designed for monotonically increasing values (like energy meters) where HA compensates for detected resets. The Tandem API returns *daily-reset accumulators* — they reset to 0 at midnight, not per-meter-rollover. HA's sum statistics would be nonsensical across day boundaries.

**3. Use `state_class=TOTAL`**
Rejected. `TOTAL` is designed for the Energy dashboard integration. It does not produce the mean/min/max statistics needed for Statistics Graph cards.

## Consequences

- Statistics Graph cards work correctly with accurate event-level timestamps
- `carelink.import_history` service action can backfill months of history using the same `_import_statistics()` pipeline
- **The 6 LTS statistic IDs are independent of sensor entity `state_class`** — changes to sensor metadata do not affect historical statistics
- Daily/weekly history requires periodic polling (automatic on each coordinator update) or manual `import_history` call
- Upstream integration (noiwid/HAFamilyLink) had no LTS implementation — this is entirely post-fork code
