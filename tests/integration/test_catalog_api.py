def test_services_endpoint_returns_three_mvp_services(client):
    account = client.post("/v1/accounts").json()

    response = client.get("/v1/services", headers={"X-API-Key": account["api_key"]})

    assert response.status_code == 200
    assert response.json() == {
        "services": [
            {
                "service_key": "search.web",
                "pricing_mode": "fixed",
                "fixed_cost_micro_usdc": 100_000,
            },
            {
                "service_key": "ocr.parse_image",
                "pricing_mode": "fixed",
                "fixed_cost_micro_usdc": 200_000,
            },
            {
                "service_key": "llm.chat",
                "pricing_mode": "reserve_then_settle",
                "input_cost_per_1k_micro_usdc": 50_000,
                "output_cost_per_1k_micro_usdc": 100_000,
                "reserve_buffer_bps": 12000,
            },
        ]
    }
