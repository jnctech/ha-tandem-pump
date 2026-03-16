# ADR-011: CGM Multi-Source Routing

**Date:** 2026-03-16
**Status:** Proposed

## Context

The integration supports three CGM sources — Dexcom G6 (event 256), G7 (event 399), and FreeStyle Libre 2 (event 372). A decision was made in Phase 3 (CR-010) to route all three through the same `cgm_readings` pipeline, with sensor type detection via AA_DAILY_STATUS (event 313).

## Decision

*To be documented — routing strategy, sensor type precedence, and layout differences need formal capture.*

## Consequences

*To be documented.*
