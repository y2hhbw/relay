from tests.conftest import create_funded_account


def test_ocr_call_uses_fixed_cost_billing(client):
    account = create_funded_account(client, amount_micro_usdc=500_000)

    response = client.post(
        "/v1/calls/ocr.parse_image",
        headers={"X-API-Key": account["api_key"]},
        json={"image_url": "https://example.com/receipt.png"},
    )
    balance = client.get("/v1/balance", headers={"X-API-Key": account["api_key"]})

    assert response.status_code == 200
    assert response.json()["billing"] == {
        "pricing_mode": "fixed",
        "debited_micro_usdc": 200_000,
    }
    assert balance.json() == {
        "available_micro_usdc": 300_000,
        "reserved_micro_usdc": 0,
    }
