# Security Policy

## Supported Versions

Relay is an early-stage project. Security fixes, when made, will generally target the latest version in the default branch.

## Reporting a Vulnerability

Please do not open a public issue for a security-sensitive bug.

Instead, report it privately to the maintainer with:

- a clear description of the issue
- affected files or endpoints
- reproduction steps
- impact assessment
- any suggested mitigation, if available

If you are unsure whether something is security-sensitive, treat it as sensitive first.

## Scope Notes

Areas especially worth reporting:

- authentication or API key handling flaws
- billing integrity issues
- deposit attribution or idempotency bugs
- cursor or query tampering issues
- listener behavior that could mis-credit funds

This project is still an MVP, so some known operational limitations are already documented in [README.md](README.md) and [docs/mvp-implementation.md](docs/mvp-implementation.md).
