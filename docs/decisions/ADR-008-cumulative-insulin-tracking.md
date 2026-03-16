# ADR-008: Cumulative Seq-Based Insulin Tracking

**Date:** 2026-03-16
**Status:** Proposed

## Context

Estimated remaining insulin is computed by subtracting cumulative deliveries from cartridge fill volume. The 14-day API event window means events age out, creating a drift risk. A decision was made in Phase 6 (CR-015) to use seq-based cumulative tracking rather than recomputing from the event window each poll.

## Decision

*To be documented — decision was made in CR-015 but not captured as an ADR.*

## Consequences

*To be documented.*
