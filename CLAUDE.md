# Tandem Source / Carelink Integration

Home Assistant custom integration for Tandem t:slim insulin pumps via Medtronic Carelink.

## Project Structure
- Main code: `custom_components/carelink/`
- Key files: `tandem_api.py` (API client), `__init__.py` (coordinator), `const.py` (sensors), `sensor.py` (entities)
- Scripts: `scripts/check_api_drift.py`, `scripts/generate_sensor_docs.py`
- Fixtures: `tests/fixtures/known_good_api_response.json`
- AI review audit trail: `docs/reviews/`
- Change register: `docs/CHANGE-REGISTER.md` — significant changes, one CR per PR
- Issue tracker: `docs/ISSUES.md` — repo-specific issues, features, and planned work

## Development
- Branch strategy: Git Flow (develop, feature/*, bugfix/*, release/*)
- Commit style: Conventional Commits (`fix(tandem):`, `feat:`, `docs:`, etc.)
- Credentials: `test_credentials.json` (gitignored), template at `test_credentials.json.template`
- Deploy to HA: `scp -i ~/.ssh/ha_debug_ed25519 <file> root@192.168.88.43:/config/custom_components/carelink/`
- Restart HA: `ssh -i ~/.ssh/ha_debug_ed25519 root@192.168.88.43 "ha core restart"`
- Tests need Python 3.12 + `pytest-homeassistant-custom-component` (not available on Win/Py3.13)
- **Do NOT run code-simplifier on `fix/security-*` branches** — it reverts intentional defensive patterns

## Ruff Format (IMPORTANT — CI will fail without this)
Always run before committing:
```
python -m ruff format custom_components/carelink tests
```
- Use `python -m ruff` (not bare `ruff` — not in PATH on Windows)
- A pre-commit hook at `.git/hooks/pre-commit` auto-formats staged files on each commit
- The hook is maintained manually (OneDrive-hosted `.git` prevents `pre-commit install`)
- CI runs `ruff format --check` on every push — format failures block merge

## Key Notes
- ControlIQ API endpoints return 404 - do not rely on them
- Docker protection mode is ON on HA - cannot access container directly
- Branch protection on master + develop: required checks wired up (ISS-003 closed 2026-03-12)
- Gitea (192.168.30.10) is inner-loop CI only — no branch protection, not source of truth
- Small codebase (~20 source files) — use Grep/Glob before reaching for Explore agents

## AI Assistant Usage

| Task | Model |
|------|-------|
| Implementation (coding, testing, file changes) | Claude Sonnet 4.6 |
| Architectural decisions, release reviews, design trade-offs | Claude Opus 4.6 |

Default to Sonnet. Use Opus only when a decision is genuinely unresolved at the architectural level.

## Quality Gate — Hard Constraints

SonarCloud gate is **blocking** (no `continue-on-error`). Targets:

| Rule | Limit |
|------|-------|
| Cognitive complexity | < 15 per function |
| Coverage | ≥ 80% lines (excluding tests/) |
| Duplication | 0% |
| Bugs / Vulnerabilities / Code Smells | Grade "A" |

## Pre-PR Checklist (this repo)

1. `pytest tests/ -v` — 100% passing
2. `python -m ruff format --check custom_components/carelink tests` — format clean
3. `bandit -c bandit.yaml -r custom_components/carelink` — clean
4. `python scripts/check_api_drift.py` — no drift (if `tandem_api.py` or `__init__.py` changed)
5. `pr-review-toolkit:silent-failure-hunter` — no silent failures
6. `pr-review-toolkit:code-reviewer` — logic/intent review
7. `/hacs-review` — HACS compliance, async safety, coordinator, lifecycle, entity patterns (fills gaps pr-review-toolkit doesn't cover)
8. **Skip `code-simplifier`** — SonarCloud Grade A covers complexity/duplication/smells
9. **ADR check** — if PR changes data formats, entity identity, API contracts, or migration behaviour, create/update an ADR in `docs/decisions/`
10. Docs updated (README, CONTRIBUTING.md, info.md as needed)
11. Branch up to date with develop
12. PR targets `develop` (not master)

## Security Conventions

- `test_credentials.json` gitignored, template at `test_credentials.json.template`
- Never commit real credentials, API tokens, or session cookies
- Gitleaks scanning in CI (full history) and pre-commit hook (HEAD scan)

## HA Integration Rules
See [docs/internal/ha-integration-rules.md](docs/internal/ha-integration-rules.md) — async safety, entity patterns, coordinator conventions, config flow, lifecycle, error handling. Follow these when writing or modifying integration code.

## Agent Context

### Key File Boundaries
- **API client** (`tandem_api.py`): HTTP + response parsing only — no HA imports, no coordinator logic
- **Coordinator** (`__init__.py`): orchestration only — no direct HTTP calls, no sensor definitions
- **Sensor definitions** (`const.py`): declarative data only — no logic, no API imports
- **Sensor entities** (`sensor.py`): entity creation from const.py definitions — no business logic
- **Scripts** (`scripts/`): standalone tools — no imports from custom_components/

### Bash Deny List
- `scp` or `ssh` to production HA without explicit user confirmation
- `rm -rf` without explicit path
- `pip install` in global scope (use `--user` or venv)

## Scope Boundary

This integration reads data from the Tandem Source / Carelink API. It does NOT:
- Write to the pump or modify therapy settings
- Implement ControlIQ endpoints (return 404 — confirmed, do not retry)
- Modify upstream patterns from noiwid/HAFamilyLink without explicit request
- Access the HA container directly (Docker protection mode ON)

If a task appears to require any of the above, stop and flag it.

## Test Conventions

- **Runner:** pytest with pytest-homeassistant-custom-component
- **Location:** `tests/` directory (not co-located — HA integration convention)
- **Fixtures:** `tests/fixtures/` — known-good API responses, mock data
- **Test helpers:** `tests/conftest.py` — shared fixtures and mocks
- **What to test:** coordinator data parsing, sensor value computation, API response handling, error paths
- **What not to test:** HA framework internals, sensor platform registration boilerplate
- **Environment:** Python 3.12 required (pytest-homeassistant-custom-component not available on 3.13)
- **Run locally:** Docker host via ssh, or dev container
