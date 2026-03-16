# ADR-007: Entity unique_id Format Includes entry_id

**Date:** 2026-03-16
**Status:** Accepted

## Context

HA entities require a stable `unique_id` for the entity registry. The original format was `{DOMAIN}_{sensor_key}` (e.g. `carelink_last_glucose_level`). This works for single-entry setups but causes entity collisions if a user adds two config entries (e.g. Tandem + Carelink, or two Tandem accounts for different family members).

HACS review finding ENT-01 flagged this as a compliance issue — HA best practice is to scope entity identity to the config entry.

## Decision

Include the config entry ID in entity `unique_id`:

```
{DOMAIN}_{entry.entry_id}_{sensor_key}
```

Example: `carelink_a1b2c3d4e5f6_last_glucose_level`

## Consequences

**Positive:**
- Multi-entry setups work correctly — no entity collisions
- Compliant with HA integration best practices
- Future-proofs for Care Partner scenarios (monitoring multiple pumps)

**Negative:**
- **Breaking change on upgrade** — all existing entities get new unique_ids. HA creates new entity registry entries (with `_2` suffix), old ones become orphaned `unavailable` shells.
- **One-time cleanup required** — users must delete the integration and re-add it, or manually delete orphaned entities and rename `_2` entities.
- **History loss** — long-term statistics are tied to entity IDs, not unique_ids. Reinstalling the integration loses the association. Explicit LTS imports (ADR-001) are unaffected as they use `statistic_id` not `entity_id`.

## Alternatives Considered

1. **Keep old format** — no upgrade pain, but blocks multi-entry support. Deferred initially, then reversed.
2. **Entity migration in `async_setup_entry`** — programmatically rename old entity registry entries to new unique_ids. Correct but adds complexity for a small user base pre-HACS approval.
3. **Use `async_migrate_entry`** — HA's built-in migration hook. Same complexity as option 2.

Option 2/3 should be implemented before the next version bump if the user base grows post-HACS approval.
