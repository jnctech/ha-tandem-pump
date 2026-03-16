# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| Latest release | Yes |
| Older releases | No — please upgrade |

## Reporting a Vulnerability

**Please do not report security vulnerabilities through public GitHub issues.**

Use GitHub's private vulnerability reporting:

1. Go to the [Security tab](../../security/advisories) of this repository
2. Click **"Report a vulnerability"**
3. Describe the issue, steps to reproduce, and potential impact

I'll review and respond as soon as practical.

## Scope

This integration stores and transmits Tandem Source (and optionally Medtronic CareLink) login credentials. Vulnerabilities relating to credential exposure, session token handling, or data leakage are the highest priority.

## Out of scope

- Vulnerabilities in Home Assistant core (report to [home-assistant/core](https://github.com/home-assistant/core))
- Vulnerabilities in the Tandem Source or CareLink platforms themselves
- Theoretical vulnerabilities with no practical exploit path

## Automated Security Controls

- **Gitleaks** — secret scanning in CI and pre-commit hook
- **Bandit** — Python static security analysis on every push
- **pip-audit** — dependency vulnerability scanning
- **Dependabot** — automated dependency updates for Python packages and GitHub Actions
- **OpenSSF Scorecard** — supply chain security assessment (results in GitHub Security tab)
- **Dependency Review** — blocks PRs that introduce dependencies with known vulnerabilities
- **SonarCloud** — continuous code quality and security analysis (blocking quality gate)
- **SHA-pinned actions** — all GitHub Actions references use commit SHAs
