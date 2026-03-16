from tests.conftest import create_funded_account


def test_search_request_requires_query_field(client):
    account = create_funded_account(client)

    response = client.post(
        "/v1/calls/search.web",
        headers={"X-API-Key": account["api_key"]},
        json={},
    )

    assert response.status_code == 422


def test_llm_request_requires_max_output_tokens(client):
    account = create_funded_account(client)

    response = client.post(
        "/v1/calls/llm.chat",
        headers={"X-API-Key": account["api_key"]},
        json={
            "prompt": "hello",
            "model": "gpt-mini",
        },
    )

    assert response.status_code == 422


def test_search_request_rejects_unknown_fields(client):
    account = create_funded_account(client)

    response = client.post(
        "/v1/calls/search.web",
        headers={"X-API-Key": account["api_key"]},
        json={
            "query": "relay",
            "unexpected": "field",
        },
    )

    assert response.status_code == 422
