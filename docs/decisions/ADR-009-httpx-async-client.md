# ADR-009: Own httpx.AsyncClient vs HA Shared Session

**Date:** 2026-03-16
**Status:** Proposed

## Context

HA integrations conventionally use `async_get_clientsession(hass)` for HTTP requests. This integration uses its own `httpx.AsyncClient` instances in `api.py`, `tandem_api.py`, and `nightscout_uploader.py`. HACS review finding A-4a flagged this as a divergence. The decision to defer was made in ISS-012.

## Decision

*To be documented — accepted risk rationale needs formal capture.*

## Consequences

*To be documented.*
