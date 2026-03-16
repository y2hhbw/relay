from tests.conftest import create_funded_account
from app.models import ApiCall


def test_fixed_cost_call_debits_balance(client):
    account = create_funded_account(client)

    response = client.post(
        "/v1/calls/search.web",
        headers={"X-API-Key": account["api_key"]},
        json={"query": "latest ai papers"},
    )
    balance = client.get("/v1/balance", headers={"X-API-Key": account["api_key"]})

    assert response.status_code == 200
    assert response.json()["billing"] == {
        "pricing_mode": "fixed",
        "debited_micro_usdc": 100_000,
    }
    assert balance.json() == {
        "available_micro_usdc": 400_000,
        "reserved_micro_usdc": 0,
    }

    session = client.app.state.session_factory()
    try:
        calls = session.query(ApiCall).all()
        assert len(calls) == 1
        assert calls[0].service_key == "search.web"
        assert calls[0].status == "succeeded"
        assert calls[0].settled_micro_usdc == 100_000
    finally:
        session.close()


def test_fixed_cost_call_refunds_if_provider_fails(client):
    account = create_funded_account(client)

    response = client.post(
        "/v1/calls/search.web",
        headers={"X-API-Key": account["api_key"]},
        json={"query": "fail"},
    )
    balance = client.get("/v1/balance", headers={"X-API-Key": account["api_key"]})

    assert response.status_code == 502
    assert response.json()["detail"] == "Upstream provider failed"
    assert balance.json() == {
        "available_micro_usdc": 500_000,
        "reserved_micro_usdc": 0,
    }

    session = client.app.state.session_factory()
    try:
        calls = session.query(ApiCall).all()
        assert len(calls) == 1
        assert calls[0].service_key == "search.web"
        assert calls[0].status == "failed"
        assert calls[0].error_text == "upstream_provider_failed"
    finally:
        session.close()
