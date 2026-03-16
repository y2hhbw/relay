def test_confirmed_deposit_credits_balance_once(client):
    account = client.post("/v1/accounts").json()

    deposit_payload = {
        "tx_hash": "0xabc",
        "log_index": 1,
        "deposit_address": account["deposit_address"],
        "amount_micro_usdc": 1_500_000,
    }

    first = client.post("/internal/deposits/confirm", json=deposit_payload)
    second = client.post("/internal/deposits/confirm", json=deposit_payload)
    balance = client.get("/v1/balance", headers={"X-API-Key": account["api_key"]})

    assert first.status_code == 202
    assert first.json()["status"] == "credited"
    assert second.status_code == 202
    assert second.json()["status"] == "duplicate"
    assert balance.status_code == 200
    assert balance.json() == {
        "available_micro_usdc": 1_500_000,
        "reserved_micro_usdc": 0,
    }


def test_unknown_deposit_address_is_ignored(client):
    response = client.post(
        "/internal/deposits/confirm",
        json={
            "tx_hash": "0xdef",
            "log_index": 0,
            "deposit_address": "0x0000000000000000000000000000000000000001",
            "amount_micro_usdc": 500_000,
        },
    )

    assert response.status_code == 202
    assert response.json()["status"] == "ignored"
