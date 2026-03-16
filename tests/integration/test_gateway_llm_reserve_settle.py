from app.models import ApiCall


def _fund_account(client, amount_micro_usdc: int = 2_000_000) -> dict[str, str]:
    account = client.post("/v1/accounts").json()
    client.post(
        "/internal/deposits/confirm",
        json={
            "tx_hash": f"0x{amount_micro_usdc:x}",
            "log_index": 1,
            "deposit_address": account["deposit_address"],
            "amount_micro_usdc": amount_micro_usdc,
        },
    )
    return account


def test_llm_call_reserves_then_settles_actual_usage(client):
    account = _fund_account(client)

    response = client.post(
        "/v1/calls/llm.chat",
        headers={"X-API-Key": account["api_key"]},
        json={
            "prompt": "hello relay",
            "model": "gpt-mini",
            "max_output_tokens": 1000,
        },
    )
    balance = client.get("/v1/balance", headers={"X-API-Key": account["api_key"]})

    assert response.status_code == 200
    assert response.json()["billing"] == {
        "pricing_mode": "reserve_then_settle",
        "reserved_micro_usdc": 126_000,
        "settled_micro_usdc": 25_000,
        "released_micro_usdc": 101_000,
    }
    assert balance.json() == {
        "available_micro_usdc": 1_975_000,
        "reserved_micro_usdc": 0,
    }

    session = client.app.state.session_factory()
    try:
        calls = session.query(ApiCall).all()
        assert len(calls) == 1
        assert calls[0].service_key == "llm.chat"
        assert calls[0].status == "succeeded"
        assert calls[0].reserved_micro_usdc == 126_000
        assert calls[0].settled_micro_usdc == 25_000
    finally:
        session.close()


def test_llm_call_rejects_when_balance_cannot_cover_reserve(client):
    account = _fund_account(client, amount_micro_usdc=100_000)

    response = client.post(
        "/v1/calls/llm.chat",
        headers={"X-API-Key": account["api_key"]},
        json={
            "prompt": "hello relay",
            "model": "gpt-mini",
            "max_output_tokens": 1000,
        },
    )

    assert response.status_code == 402
    assert response.json()["detail"] == "Insufficient available balance for reserve"

    session = client.app.state.session_factory()
    try:
        calls = session.query(ApiCall).all()
        assert len(calls) == 1
        assert calls[0].service_key == "llm.chat"
        assert calls[0].status == "rejected"
        assert calls[0].error_text == "insufficient_reserve_balance"
    finally:
        session.close()
