# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| Latest release | Yes |
| Older releases | No — please upgrade |

## Reporting a Vulnerability

**Please do not report security vulnerabilities through public GitHub issues.**

### Preferred method: GitHub Security Advisories

1. Go to the [Security tab](../../security/advisories) of this repository
2. Click **"Report a vulnerability"**
3. Fill in the details — include steps to reproduce, impact, and any suggested fixes

### Alternative: Email

Email **security@jnctech.co.uk** with:
- A description of the vulnerability
- Steps to reproduce
- Potential impact
- Any suggested mitigations

### Response timeline

- **Acknowledgement:** within 48 hours
- **Initial assessment:** within 7 days
- **Fix or mitigation:** dependent on severity and complexity

We will coordinate disclosure with you before publishing any advisory.

## Scope

This integration handles authentication credentials for Medtronic Carelink and Tandem t:slim pump accounts. Vulnerabilities relating to credential exposure, session token handling, or data leakage are considered high priority.

## Out of scope

- Vulnerabilities in Home Assistant core (report to [home-assistant/core](https://github.com/home-assistant/core))
- Vulnerabilities in the Carelink or Tandem platforms themselves
- Theoretical vulnerabilities with no practical exploit path

## Security Measures

This project uses the following automated security controls:

- **Gitleaks** — secret scanning on every push and PR (full history)
- **Bandit** — Python static analysis for common security issues
- **pip-audit** — dependency vulnerability scanning against known CVE databases
- **Dependabot** — automated dependency updates for Python packages and GitHub Actions
- **OpenSSF Scorecard** — weekly supply chain security assessment (results in GitHub Security tab)
- **Dependency Review** — blocks PRs that introduce dependencies with known vulnerabilities
- **SonarCloud** — continuous code quality and security analysis (blocking quality gate)
- **SHA-pinned actions** — all GitHub Actions references use commit SHAs to prevent supply chain attacks
