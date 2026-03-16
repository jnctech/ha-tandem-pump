# ADR-010: Binary Event Decoding Strategy

**Date:** 2026-03-16
**Status:** Proposed

## Context

Tandem pump events are returned as base64-encoded binary payloads with event-type-specific struct layouts. The integration uses `struct.unpack` to decode battery, USB, shelf mode, cartridge, CGM, bolus, and alert/alarm events. Layout assumptions are derived from tconnectsync and reverse engineering.

## Decision

*To be documented — struct layout documentation and validation strategy needs formal capture.*

## Consequences

*To be documented.*
