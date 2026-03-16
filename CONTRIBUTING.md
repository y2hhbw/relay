# Contributing to Relay

Relay is still an MVP backend. The fastest way to help is to keep changes small, concrete, and tied to the current system boundary.

## Before You Start

- Read [README.md](README.md) for the current scope.
- Read [docs/mvp-implementation.md](docs/mvp-implementation.md) before proposing larger changes.
- If your change expands the product scope, explain why the current MVP boundary is insufficient.

## Local Setup

Create a virtual environment:

```bash
python3 -m venv .venv
```

Install development dependencies:

```bash
.venv/bin/python -m pip install -e '.[dev]'
```

If your work touches the chain listener:

```bash
.venv/bin/python -m pip install -e '.[dev,chain]'
```

## Running the Project

Start the API:

```bash
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Run the local smoke flow:

```bash
bash scripts/manual_smoke.sh
```

If port `8000` is already in use:

```bash
PORT=8011 bash scripts/manual_smoke.sh
```

## Tests

Run the test suite:

```bash
.venv/bin/pytest -q
```

Run a syntax pass:

```bash
python3 -m compileall app tests
```

## Pull Requests

Please keep pull requests focused.

Good pull requests usually:

- solve one problem
- include tests when behavior changes
- update docs when setup, behavior, or scope changes
- explain tradeoffs instead of only describing code changes

For larger changes, open an issue first so the approach can be checked against the current roadmap.

## Good Areas to Contribute

- real provider integrations
- Redis-backed rate limiting
- listener observability
- query hardening
- operational tooling

## Out of Scope for This MVP

These are not good starter PRs unless discussed first:

- automated payouts to upstream providers
- broad product-scope expansion unrelated to prepaid API usage
- replacing the lightweight operational model with a heavy monitoring stack by default
