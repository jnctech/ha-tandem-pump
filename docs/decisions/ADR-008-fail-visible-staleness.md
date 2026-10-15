# ADR-008: Fail-visible staleness for decision-input sensors (safety)

**Date:** 2026-07-10
**Status:** Accepted

## Context

This integration surfaces **decision-input** values — glucose, insulin-on-board, basal rate —
that a user or automation may act on. Data arrives via the Tandem Source cloud, which the pump
uploads to periodically (roughly hourly), not in real time. An earlier "diagnostic mode" made
sensors **bypass** the staleness check and always show their last known value, so a reading from
hours ago rendered identically to a live one.

The oob estate standard `STANDARD-stable-anchor-reconciliation-2026-07-02` (relayed) is
load-bearing here: fail-closed control logic that goes silent is a **safety event, not
cosmetic** for an insulin/glucose integration — a silently-dead decision input looks fine while
being wrong. The standard's rule 3: keep the safe behaviour but **add a named visibility surface**.

## Decision

Make staleness **fail-visible**, in `entity.py` (`TandemEntity.available`) as the single source
of truth:

- **Decision-input sensors go `unavailable`** when the pump upload is older than
  `TANDEM_DATA_STALE_TIMEDELTA` (6 h). HA then stops recording them and does not present a stale
  value as current.
- **IOB has its own, shorter gate** (2026-10-15): Tandem Source reports IOB only on bolus events
  and does not decay it, so it goes `unavailable` once the bolus that carried it is older than
  `TANDEM_IOB_MAX_AGE` (60 min), even when the upload is fresh. Found live: a 4 h-old IOB read
  several units while the pump showed 0 after a reboot.
- **Timestamp / settings sensors stay available** (`TANDEM_SENSORS_ALWAYS_AVAILABLE`) so the user
  can always see *when* data last arrived and what pump is connected.
- **A named health surface:** `binary_sensor.tandem_data_stale` (`device_class=problem`,
  diagnostic) turns **on** when data is stale. It is *always* available (only a coordinator
  failure takes it offline) so the indicator can never silently hide itself.
- **Stable anchor (rule 1):** entity `unique_id` is `f"{DOMAIN}_{entry_id}_{key}"` — anchored on
  the immutable config `entry_id`, never a mutable/externally-owned label that could re-derive.

## Alternatives Considered

- **Keep diagnostic mode (always show last value).** Simple, but exactly the silent-stale failure
  the safety standard forbids. Rejected.
- **Hard-error on stale data.** Trades a silent stall for an outright outage and can freeze
  automations; the standard explicitly warns against this. Rejected in favour of unavailable +
  visibility surface.

## Consequences

- Users see decision-input sensors go `unavailable` during long sync gaps — intended, and
  documented in TROUBLESHOOTING.
- Tests assert the fail-visible contract directly (`tests/test_tandem_stale_data.py`,
  `tests/test_sensor_golden.py::test_stale_data_marks_decision_inputs_unavailable`); a regression
  that served stale glucose as live fails the suite.
- The health binary_sensor is a standing detection control, catching the *next* stale episode.
