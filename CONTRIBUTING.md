# Contributing to Tandem Source / Carelink Integration

Thank you for contributing. This document covers everything you need to get started.

## Prerequisites

| Tool | Purpose |
|------|---------|
| [Docker Desktop](https://www.docker.com/products/docker-desktop/) | Dev container and test container |
| [VS Code](https://code.visualstudio.com/) | Recommended editor |
| [Remote - Containers](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers) | VS Code dev container support |
| Git | Version control |

Python 3.12 is required for tests. The dev container provides it — no local Python install needed.

---

## Dev Container Setup

The recommended way to contribute is via the dev container. It provides Python 3.12, all dependencies, Ruff, Bandit, and Gitleaks pre-installed.

1. Clone the repository and open it in VS Code
2. When prompted, click **"Reopen in Container"** (or run `Dev Containers: Reopen in Container` from the command palette)
3. VS Code will build the container and install all dependencies automatically

That's it — the environment is ready.

---

## Running Tests

**Locally (requires Python 3.12):**
```bash
pytest tests/ -v
```

**Via test container (recommended — reproducible, no local Python needed):**
```bash
docker compose -f docker-compose.test.yml run --rm tests
```

Run a single test file:
```bash
docker compose -f docker-compose.test.yml run --rm tests tests/test_tandem_api.py -v
```

---

## Linting and Formatting

This project uses [Ruff](https://docs.astral.sh/ruff/) for both linting and formatting.

```bash
# Lint
python -m ruff check custom_components/carelink tests

# Format
python -m ruff format custom_components/carelink tests

# Format check only (what CI runs)
python -m ruff format --check custom_components/carelink tests
```

A pre-commit hook auto-formats staged files on each commit. CI will fail if files are not formatted — run `ruff format` before pushing.

---

## Secret Scanning (Gitleaks)

[Gitleaks](https://gitleaks.io/) is installed in the dev container and runs as a pre-commit hook. It scans for accidentally committed secrets.

Run manually:
```bash
gitleaks detect --config .gitleaks.toml
```

CI runs a full history scan on every push. If the CI `secrets` job fails, Gitleaks has found a potential secret — review the output and add an allowlist entry to `.gitleaks.toml` if it is a false positive.

---

## Branch Strategy

We follow [Git Flow](https://nvie.com/posts/a-successful-git-branching-model/):

| Branch | Purpose |
|--------|---------|
| `master` | Latest stable release |
| `develop` | Integration branch — all PRs target here |
| `feature/*` | New features |
| `bugfix/*` | Bug fixes |
| `release/*` | Release preparation |

```bash
git checkout develop
git pull origin develop
git checkout -b feature/your-feature-name
```

---

## Claude Code Agent

This project uses [Claude Code](https://claude.ai/claude-code) for AI-assisted development.

**Configuration:** `CLAUDE.md` in the project root.

**Model usage:**

| Task | Model |
|------|-------|
| Implementation (coding, testing, file changes) | Claude Sonnet 4.6 |
| Architectural decisions, release reviews, design trade-offs | Claude Opus 4.6 |

**Useful prompts for new sessions:**
- `"Read CLAUDE.md and the plan at C:\Users\jc\.claude\plans\lexical-puzzling-piglet.md then continue implementation"`
- `"Run the baseline AI review across the full codebase and output to docs/reviews/review-baseline-YYYY-MM-DD.md"`

**Note:** All AI-assisted contributions go through the same CI gates and quality bar as human-written code. What matters is the code, not how it was written.

---

## PR Checklist

Before opening a PR, verify:

- [ ] All tests pass: `pytest tests/ -v`
- [ ] Ruff lint clean: `python -m ruff check custom_components/carelink tests`
- [ ] Ruff format clean: `python -m ruff format --check custom_components/carelink tests`
- [ ] Bandit clean: `bandit -c bandit.yaml -r custom_components/carelink`
- [ ] Coverage maintained — SonarCloud will check (target: >= 80%)
- [ ] PR title is descriptive (not the branch name)
- [ ] PR description includes **Summary** and **Test Plan** sections
- [ ] PR targets `develop` (not `master`)

---

## Commit Guidelines

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <subject>

<body — explain the why, not just the what>
```

**Types:** `feat`, `fix`, `docs`, `test`, `refactor`, `chore`, `ci`

**Examples:**
```
feat(tandem): add support for Control-IQ suspend events

fix(api): resolve blocking SSL call in TandemSourceClient
- Move SSL context creation to executor
- Fixes #123

chore(deps): bump httpx from 0.23.0 to 0.27.0
```

---

## Quality Bar

We don't care whether your code is AI-assisted or handwritten — the quality bar is the same. Every PR passes the same CI gates, the same SonarCloud quality gate, and the same review process. What matters is the code, not how it was written.

**SonarCloud targets (gate configured in UI):**

| Metric | Target |
|--------|--------|
| Line coverage | >= 80% (excluding tests/) |
| Cognitive complexity | < 15 per function |
| Duplication | 0% |
| Bugs / Vulnerabilities / Code Smells | Grade "A" |

---

## Getting Help

- Open an issue for bugs or feature requests
- Check [README.md](README.md) for setup and configuration help
- Review [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for common issues
