# ADR-012: Auth Lifecycle and Reauth Flow

**Date:** 2026-03-16
**Status:** Accepted

## Context

When API credentials expire or become invalid, the integration needs to notify the user and provide a way to re-authenticate. HA provides two mechanisms:

1. **`UpdateFailed`** — coordinator retries on next poll interval. The integration shows as "unavailable" but the user gets no actionable prompt.
2. **`ConfigEntryAuthFailed`** — HA automatically triggers a reauth flow, showing a notification with a "Reconfigure" button that routes to `async_step_reauth`.

The Tandem and Carelink API clients have different auth failure semantics:
- **Tandem** (`TandemSourceClient`): raises `TandemAuthError` on credential failure
- **Carelink** (`CarelinkClient`): `login()` returns `False` on auth failure, raises exceptions on network errors

## Decision

### Tandem coordinator
Catch `TandemAuthError` separately and raise `ConfigEntryAuthFailed`. Generic exceptions raise `UpdateFailed` (network errors should retry, not prompt reauth).

### Carelink coordinator
Split login from data fetch. Check `login()` return value — `False` raises `ConfigEntryAuthFailed`, exceptions raise `UpdateFailed`.

### Reauth flow
Single `async_step_reauth_confirm` handles both platforms. Detects platform from config entry data, shows the appropriate credential form, validates, updates the entry, and reloads.

## Consequences

**Positive:**
- Users get an actionable HA notification when credentials expire
- Automatic retry stops (prevents rate limiting with bad credentials)
- Single reauth step handles both platforms via schema selection

**Negative:**
- Carelink auth failure detection is heuristic — `login()` returning `False` could be a transient issue, not permanent credential expiry. Accepted risk: reauth prompt is low-cost for the user.
- Reauth `strings.json` entry lists both platform field sets — HA only renders schema fields so no runtime impact, but translation files are slightly cluttered.

## Alternatives Considered

1. **Keep `UpdateFailed` for all auth errors** — simpler, but user never gets prompted to fix credentials. Integration retries with bad creds indefinitely.
2. **Add `CarelinkAuthError`** to upstream `api.py` — cleaner, but `api.py` is upstream fork code. Minimising upstream divergence is a project goal.
