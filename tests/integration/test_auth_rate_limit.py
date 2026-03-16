from tests.conftest import create_funded_account


def test_calls_require_api_key(client):
    response = client.post("/v1/calls/search.web", json={"query": "hello"})

    assert response.status_code == 401


def test_rate_limit_is_per_account_and_service(client):
    first_account = create_funded_account(client, amount_micro_usdc=1_000_000)
    second_account = create_funded_account(client, amount_micro_usdc=1_000_000)

    for _ in range(3):
        ok = client.post(
            "/v1/calls/search.web",
            headers={"X-API-Key": first_account["api_key"]},
            json={"query": "latest ai papers"},
        )
        assert ok.status_code == 200

    limited = client.post(
        "/v1/calls/search.web",
        headers={"X-API-Key": first_account["api_key"]},
        json={"query": "latest ai papers"},
    )
    other_service = client.post(
        "/v1/calls/ocr.parse_image",
        headers={"X-API-Key": first_account["api_key"]},
        json={"image_url": "https://example.com/receipt.png"},
    )
    other_account = client.post(
        "/v1/calls/search.web",
        headers={"X-API-Key": second_account["api_key"]},
        json={"query": "latest ai papers"},
    )

    assert limited.status_code == 429
    assert limited.json()["detail"] == "Rate limit exceeded"
    assert other_service.status_code == 200
    assert other_account.status_code == 200
