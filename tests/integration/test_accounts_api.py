def test_create_account_returns_api_key_and_deposit_address(client):
    response = client.post("/v1/accounts")

    assert response.status_code == 201
    payload = response.json()

    assert payload["account_id"]
    assert payload["api_key"].startswith("relay_")
    assert payload["deposit_address"].startswith("0x")
    assert len(payload["deposit_address"]) == 42


def test_balance_starts_at_zero_and_requires_api_key(client):
    create_response = client.post("/v1/accounts")
    api_key = create_response.json()["api_key"]

    unauthorized = client.get("/v1/balance")
    assert unauthorized.status_code == 401

    authorized = client.get(
        "/v1/balance",
        headers={"X-API-Key": api_key},
    )

    assert authorized.status_code == 200
    assert authorized.json() == {
        "available_micro_usdc": 0,
        "reserved_micro_usdc": 0,
    }
