#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/.venv/bin/python}"
UVICORN_BIN="${UVICORN_BIN:-$ROOT_DIR/.venv/bin/uvicorn}"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"
BASE_URL="${BASE_URL:-http://$HOST:$PORT}"
DB_PATH="${DB_PATH:-$ROOT_DIR/relay-manual.db}"
LOG_PATH="${LOG_PATH:-$ROOT_DIR/.manual-smoke-api.log}"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "missing python executable: $PYTHON_BIN" >&2
  echo "create .venv and install dependencies first" >&2
  exit 1
fi

if [[ ! -x "$UVICORN_BIN" ]]; then
  echo "missing uvicorn executable: $UVICORN_BIN" >&2
  echo "install dependencies first: .venv/bin/python -m pip install -e '.[dev]'" >&2
  exit 1
fi

export RELAY_DATABASE_URL="sqlite+pysqlite:///$DB_PATH"
export RELAY_SEARCH_PROVIDER_MODE="${RELAY_SEARCH_PROVIDER_MODE:-mock}"

server_pid=""

cleanup() {
  if [[ -n "$server_pid" ]] && kill -0 "$server_pid" >/dev/null 2>&1; then
    kill "$server_pid" >/dev/null 2>&1 || true
    wait "$server_pid" >/dev/null 2>&1 || true
  fi
}

trap cleanup EXIT

echo "starting API server on $BASE_URL"
"$UVICORN_BIN" app.main:app --host "$HOST" --port "$PORT" >"$LOG_PATH" 2>&1 &
server_pid=$!

for _ in {1..30}; do
  if ! kill -0 "$server_pid" >/dev/null 2>&1; then
    break
  fi
  if curl -fsS "$BASE_URL/docs" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

if ! curl -fsS "$BASE_URL/docs" >/dev/null 2>&1; then
  echo "API server did not become ready; log follows:" >&2
  sed -n '1,160p' "$LOG_PATH" >&2 || true
  exit 1
fi

echo "creating account"
account_response="$(curl -fsS -X POST "$BASE_URL/v1/accounts")"
echo "$account_response"

api_key="$("$PYTHON_BIN" -c 'import json,sys; print(json.load(sys.stdin)["api_key"])' <<<"$account_response")"
deposit_address="$("$PYTHON_BIN" -c 'import json,sys; print(json.load(sys.stdin)["deposit_address"])' <<<"$account_response")"

echo "initial balance"
curl -fsS -H "X-API-Key: $api_key" "$BASE_URL/v1/balance"
echo

echo "simulating deposit"
deposit_payload="$("$PYTHON_BIN" -c 'import json,sys,uuid; print(json.dumps({"tx_hash":"0x"+uuid.uuid4().hex,"log_index":0,"deposit_address":sys.argv[1],"amount_micro_usdc":1000000}))' "$deposit_address")"
curl -fsS -X POST "$BASE_URL/internal/deposits/confirm" \
  -H "Content-Type: application/json" \
  -d "$deposit_payload"
echo

echo "balance after deposit"
curl -fsS -H "X-API-Key: $api_key" "$BASE_URL/v1/balance"
echo

echo "service catalog"
curl -fsS -H "X-API-Key: $api_key" "$BASE_URL/v1/services"
echo

echo "calling search.web"
curl -fsS -X POST "$BASE_URL/v1/calls/search.web" \
  -H "X-API-Key: $api_key" \
  -H "Content-Type: application/json" \
  -d '{"query":"latest ai papers"}'
echo

echo "calling ocr.parse_image"
curl -fsS -X POST "$BASE_URL/v1/calls/ocr.parse_image" \
  -H "X-API-Key: $api_key" \
  -H "Content-Type: application/json" \
  -d '{"image_url":"https://example.com/test.png"}'
echo

echo "calling llm.chat"
curl -fsS -X POST "$BASE_URL/v1/calls/llm.chat" \
  -H "X-API-Key: $api_key" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"hello relay","model":"mock-model","max_output_tokens":200}'
echo

echo "call history"
curl -fsS -H "X-API-Key: $api_key" "$BASE_URL/v1/calls"
echo

echo "final balance"
curl -fsS -H "X-API-Key: $api_key" "$BASE_URL/v1/balance"
echo

echo "manual smoke run completed"
