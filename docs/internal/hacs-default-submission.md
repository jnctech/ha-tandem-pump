# HACS Default Store Submission — PR Description

Use this as the PR body when submitting to https://github.com/hacs/default

---

## Repository

`jnctech/ha-tandem-pump`

## Why this is a significant divergence from the upstream fork

This repository is forked from [yo-han/Home-Assistant-Carelink](https://github.com/yo-han/Home-Assistant-Carelink), a Medtronic CareLink integration. The fork adds full support for **Tandem t:slim X2 insulin pumps** via the **Tandem Source API** — an entirely different device, API, and data model.

### What's new (not in upstream)

| Area | Detail |
|---|---|
| **New API client** | `tandem_api.py` (1,139 lines) — reverse-engineered binary event protocol with 30+ event type decoders. The Tandem Source API returns pump events as raw binary data (26 bytes per event), not JSON. |
| **New coordinator** | `TandemCoordinator` (~1,900 lines) — completely separate from the original `CarelinkCoordinator`. Parses binary pump events, computes CGM statistics, tracks insulin delivery, and manages incremental state. |
| **69 Tandem-specific sensors** | Glucose monitoring (12), insulin delivery (14), pump battery (4), alerts & alarms (3), pump status (10), pump settings (11), device info (7), plus 6 long-term statistics. None of these exist upstream. |
| **Multi-CGM support** | Dexcom G6, G7, and FreeStyle Libre 2 — each with different binary layouts, auto-detected via event type. |
| **636 tests** | Upstream has essentially none. Full pytest suite with pytest-homeassistant-custom-component, 80%+ coverage, SonarCloud quality gate. |
| **CI/CD pipeline** | 14 checks per push: pytest, ruff, bandit, hassfest, HACS validation, SonarCloud, gitleaks, hadolint, actionlint, pip-audit, dependency review, OpenSSF Scorecard. |
| **Services** | `import_history` (backfill months of LTS data), `capture_diagnostics` (API schema discovery). |
| **Documentation** | 6 ADRs, API binary event reference, upstream review, troubleshooting guide. |

### What's shared with upstream

The original Medtronic CareLink coordinator (`CarelinkCoordinator`, ~375 lines) and the config flow are retained — the integration supports both Medtronic and Tandem pumps. The Medtronic path is planned for deprecation in v2.0.

### Upstream activity

The upstream repository ([yo-han/Home-Assistant-Carelink](https://github.com/yo-han/Home-Assistant-Carelink)) has had minimal updates. This fork has 120+ commits of new development since the fork point.

### Summary

This is not a minor fork — it's a new integration for a different insulin pump platform that happens to share the `carelink` domain for backwards compatibility. The Tandem Source API, binary event decoder, coordinator, sensors, tests, and CI pipeline are all original work.
