# Relay

If an AI agent is going to be a real autonomous entity, it cannot depend on a human to keep topping up its balance forever.

For an agent, tokens are not decoration. They are the material basis of its existence: the fuel for inference, the cost of calling tools, the price of staying active in the world. An agent that cannot obtain tokens for itself is still a hosted tool, no matter how good its reasoning looks. It may be capable, but its survival still depends on someone else deciding when it gets to think, act, continue, or stop. The moment an agent can acquire balance, spend it deliberately, and decide which capabilities to buy, it takes the first real step toward independent survival. If it can also earn money, recycle that income into more tokens, and keep funding its own operation, then it starts to look less like a script and more like a self-sustaining economic actor.

Relay exists to fill in that missing layer. It gives an agent the minimum financial machinery it needs to operate on its own: top up first, call services next, charge accurately, keep the ledger, and leave an audit trail. Relay is not trying to think for the agent. It is trying to make it possible for the agent to buy its own tokens, use them, and eventually learn to sustain itself.

Chinese version: [README.zh-CN.md](README.zh-CN.md)

## Problem

Most agent stacks assume API access is already funded and trusted.

In practice, that leaves an awkward gap:

- agents need money before they can call anything repeatedly
- billing models differ across services
- usage needs to be auditable
- failures should not silently lose funds
- a platform often wants to collect funds centrally and settle providers later

Relay is an attempt to make that layer explicit.

## What Exists Today

Relay is a working backend MVP.

Implemented:

- `POST /v1/accounts` creates an account, API key, and dedicated deposit address
- `GET /v1/balance` returns available and reserved balance
- `POST /v1/calls/search.web` uses fixed billing
- `POST /v1/calls/ocr.parse_image` uses fixed billing
- `POST /v1/calls/llm.chat` uses reserve-then-settle billing
- `GET /v1/calls` returns per-account audit history with filters and pagination
- an on-chain listener can poll USDC `Transfer` events and auto-credit matching deposit addresses
- a local smoke script exercises the full happy path without chain infrastructure

More detail: [docs/mvp-implementation.md](docs/mvp-implementation.md)

Product scope: [docs/mvp.md](docs/mvp.md)

## What This Repository Is Not

This repository is not:

- a production-ready multi-tenant billing control plane
- a generalized wallet product
- an automated payout system to upstream providers
- a complete observability stack

## Design Choices

These are deliberate choices, not accidents:

- One deposit address per account
  Avoids ambiguous attribution for incoming funds.
- Prepaid only
  Relay does not extend credit.
- Two billing modes in one gateway
  Fixed-cost calls and reserve-then-settle calls live behind the same API shape.
- Platform-first cash flow
  Users pay the platform; provider settlement is handled manually outside this MVP.
- Lightweight operations first
  The listener uses logs, retry/backoff, alert cooldown, and metrics snapshots instead of a full Prometheus stack.

## Current Gaps

The main missing pieces are already known:

- rate limiting is still in-memory, so multi-instance consistency is not solved
- at least one real provider should be the default production path
- listener observability needs a cleaner operational surface
- call query cursors are not signed yet

## Architecture

High-level flow:

1. client creates an account
2. Relay returns `account_id`, `api_key`, and `deposit_address`
3. user tops up that deposit address, or simulates a deposit locally
4. client calls a service through `/v1/calls/{service_key}`
5. Relay performs billing, records the call, and returns the upstream result
6. client queries balance and history through read APIs

High-level components:

- `app/main.py`: FastAPI entrypoint
- `app/listener_main.py`: chain listener entrypoint
- `app/api/`: account, catalog, gateway, internal routes
- `app/services/`: billing, deposits, rate limiting, chain listener
- `app/providers/`: upstream adapters
- `app/models.py`: SQLAlchemy models

## Upstream Provider Contract

Relay does not have a generalized plugin system yet. The upstream provider boundary is currently a code-level contract inside `app/providers/`.

That contract is intentionally small:

- provider adapters should expose a simple Python function
- successful calls should return normalized Relay-facing payloads
- upstream transport or provider failures should raise provider-specific exceptions that the gateway maps to HTTP `502`

Current contracts:

### Search provider

File: `app/providers/search.py`

Function shape:

```python
def search_web(query: str, *, provider_mode: str, timeout_seconds: float) -> dict[str, Any]:
    ...
```

Success payload:

```json
{
  "results": [
    {
      "title": "string",
      "url": "string",
      "snippet": "string, optional"
    }
  ]
}
```

Failure contract:

- raise `SearchProviderError` for upstream failures, timeouts, or invalid upstream responses
- do not return partial error payloads
- the gateway will refund fixed-cost billing and return HTTP `502`

### LLM provider

File: `app/providers/llm.py`

Function shape:

```python
def run_chat(prompt: str, model: str, max_output_tokens: int) -> dict[str, Any]:
    ...
```

Success payload:

```json
{
  "content": "string",
  "usage": {
    "input_tokens": 100,
    "output_tokens": 200
  }
}
```

Failure contract:

- raise an exception on upstream failure
- `usage.input_tokens` and `usage.output_tokens` must be integers
- `content` must be a string
- the gateway will release the reserve, mark the call as failed, and return HTTP `502`

### Notes for new provider integrations

- normalize upstream responses before they leave `app/providers/`
- keep billing inputs explicit; Relay depends on normalized token usage, not provider-specific raw metadata
- keep provider exceptions narrow and deterministic
- if a provider needs retries, authentication, or HTTP clients, keep those details inside the provider adapter rather than leaking them into the gateway layer

## Quick Start

Requirements:

- Python 3.13+

Create a virtual environment:

```bash
python3 -m venv .venv
```

Install API dependencies:

```bash
.venv/bin/python -m pip install -e '.[dev]'
```

If you want the chain listener too:

```bash
.venv/bin/python -m pip install -e '.[dev,chain]'
```

Start the API:

```bash
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

OpenAPI:

```text
http://127.0.0.1:8000/docs
```

## Manual Smoke Test

For local development, you do not need a chain RPC or listener process.

Run:

```bash
bash scripts/manual_smoke.sh
```

If port `8000` is already occupied:

```bash
PORT=8011 bash scripts/manual_smoke.sh
```

What the script does:

- starts the API
- creates an account
- simulates a deposit through the internal development endpoint
- calls `search.web`
- calls `ocr.parse_image`
- calls `llm.chat`
- prints balance and call history

## Minimal API Walkthrough

Create an account:

```bash
curl -sS -X POST http://127.0.0.1:8000/v1/accounts
```

Local development deposit simulation:

```bash
curl -sS -X POST http://127.0.0.1:8000/internal/deposits/confirm \
  -H 'Content-Type: application/json' \
  -d '{
    "tx_hash": "0xtest1",
    "log_index": 0,
    "deposit_address": "0x...",
    "amount_micro_usdc": 1000000
  }'
```

Call search:

```bash
curl -sS -X POST http://127.0.0.1:8000/v1/calls/search.web \
  -H 'X-API-Key: relay_xxx' \
  -H 'Content-Type: application/json' \
  -d '{"query":"latest ai papers"}'
```

Check balance:

```bash
curl -sS \
  -H 'X-API-Key: relay_xxx' \
  http://127.0.0.1:8000/v1/balance
```

Fetch call history:

```bash
curl -sS \
  -H 'X-API-Key: relay_xxx' \
  http://127.0.0.1:8000/v1/calls
```

## Running the Chain Listener

The listener is only required for real on-chain deposit recognition.

Required environment variables:

- `RELAY_CHAIN_LISTENER_RPC_URL`
- `RELAY_CHAIN_LISTENER_TOKEN_CONTRACT_ADDRESS`

Run:

```bash
.venv/bin/python -m app.listener_main
```

Full environment template: [.env.example](.env.example)

## Configuration

Core variables:

- `RELAY_DATABASE_URL`
- `RELAY_SEARCH_PROVIDER_MODE`
- `RELAY_SEARCH_PROVIDER_TIMEOUT_SECONDS`

Listener variables:

- `RELAY_CHAIN_LISTENER_RPC_URL`
- `RELAY_CHAIN_LISTENER_TOKEN_CONTRACT_ADDRESS`
- `RELAY_CHAIN_LISTENER_START_BLOCK`
- `RELAY_CHAIN_LISTENER_CONFIRMATIONS`
- `RELAY_CHAIN_LISTENER_POLL_INTERVAL_SECONDS`
- `RELAY_CHAIN_LISTENER_STATE_FILE_PATH`
- `RELAY_CHAIN_LISTENER_RETRY_BACKOFF_SECONDS`
- `RELAY_CHAIN_LISTENER_MAX_RETRY_BACKOFF_SECONDS`
- `RELAY_CHAIN_LISTENER_ALERT_AFTER_CONSECUTIVE_FAILURES`
- `RELAY_CHAIN_LISTENER_ALERT_COOLDOWN_SECONDS`
- `RELAY_CHAIN_LISTENER_ALERT_WEBHOOK_URL`

## Verification

Run tests:

```bash
.venv/bin/pytest -q
```

Syntax check:

```bash
python3 -m compileall app tests
```

## Roadmap

Near-term:

1. make at least one real provider the default production path
2. replace in-memory rate limiting with Redis-backed coordination
3. improve listener observability without adding a heavy metrics stack
4. add signed/HMAC cursors for query hardening

## Contributing

Start with [CONTRIBUTING.md](CONTRIBUTING.md).

If you want to work on larger changes, read [docs/mvp-implementation.md](docs/mvp-implementation.md) first so the discussion stays anchored to the actual MVP boundary.

## Support

If Relay helps you, you can support my work:

- [NOWPayments](https://nowpayments.io/payment/?iid=5525026308&source=button)
- [Buy Me a Coffee](https://www.buymeacoffee.com/hallidayyy)

## License

MIT. See [LICENSE](LICENSE).
