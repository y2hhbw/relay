from datetime import datetime, timedelta, timezone

from app.models import ApiCall
from tests.conftest import create_funded_account


def _create_call_history(client):
    account = create_funded_account(client, amount_micro_usdc=1_500_000)
    headers = {"X-API-Key": account["api_key"]}

    client.post("/v1/calls/search.web", headers=headers, json={"query": "first"})
    client.post("/v1/calls/search.web", headers=headers, json={"query": "fail"})
    client.post(
        "/v1/calls/llm.chat",
        headers=headers,
        json={"prompt": "hi", "model": "gpt-mini", "max_output_tokens": 1000},
    )
    return headers


def test_list_calls_requires_api_key(client):
    response = client.get("/v1/calls")
    assert response.status_code == 401


def test_list_calls_returns_current_account_history(client):
    headers = _create_call_history(client)

    response = client.get("/v1/calls", headers=headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 3
    assert len(payload["items"]) == 3
    statuses = {item["status"] for item in payload["items"]}
    assert "succeeded" in statuses
    assert "failed" in statuses


def test_list_calls_supports_service_and_status_filters(client):
    headers = _create_call_history(client)

    response = client.get("/v1/calls?service_key=search.web&status=failed", headers=headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["service_key"] == "search.web"
    assert payload["items"][0]["status"] == "failed"


def test_list_calls_supports_pagination(client):
    headers = _create_call_history(client)

    page_one = client.get("/v1/calls?limit=2&offset=0", headers=headers)
    page_two = client.get("/v1/calls?limit=2&offset=2", headers=headers)

    assert page_one.status_code == 200
    assert page_two.status_code == 200
    assert len(page_one.json()["items"]) == 2
    assert len(page_two.json()["items"]) == 1


def test_list_calls_supports_cursor_pagination(client):
    headers = _create_call_history(client)

    first_page = client.get("/v1/calls?limit=2", headers=headers)
    assert first_page.status_code == 200
    first_payload = first_page.json()
    assert len(first_payload["items"]) == 2
    assert first_payload["next_cursor"]

    second_page = client.get(
        f"/v1/calls?limit=2&cursor={first_payload['next_cursor']}",
        headers=headers,
    )
    assert second_page.status_code == 200
    second_payload = second_page.json()
    assert len(second_payload["items"]) == 1
    assert second_payload["next_cursor"] is None

    first_ids = {item["id"] for item in first_payload["items"]}
    second_ids = {item["id"] for item in second_payload["items"]}
    assert first_ids.isdisjoint(second_ids)


def test_list_calls_rejects_invalid_cursor(client):
    headers = _create_call_history(client)
    response = client.get("/v1/calls?cursor=not-valid-base64", headers=headers)
    assert response.status_code == 422


def test_cursor_pagination_is_stable_when_new_call_is_inserted(client):
    headers = _create_call_history(client)

    first_page = client.get("/v1/calls?limit=2", headers=headers).json()
    first_ids = {item["id"] for item in first_page["items"]}
    assert first_page["next_cursor"]

    client.post("/v1/calls/search.web", headers=headers, json={"query": "new-after-page"})

    second_page = client.get(
        f"/v1/calls?limit=2&cursor={first_page['next_cursor']}",
        headers=headers,
    ).json()
    second_ids = {item["id"] for item in second_page["items"]}

    assert len(second_page["items"]) == 1
    assert first_ids.isdisjoint(second_ids)


def test_list_calls_supports_time_range_filters(client):
    headers = _create_call_history(client)
    session = client.app.state.session_factory()
    try:
        calls = session.query(ApiCall).order_by(ApiCall.created_at.asc()).all()
        base = datetime.now(timezone.utc)
        calls[0].created_at = base - timedelta(hours=3)
        calls[1].created_at = base - timedelta(hours=2)
        calls[2].created_at = base - timedelta(hours=1)
        session.commit()
    finally:
        session.close()

    start_at = (base - timedelta(hours=2, minutes=30)).isoformat()
    end_at = (base - timedelta(hours=1, minutes=30)).isoformat()
    response = client.get(
        "/v1/calls",
        params={"start_at": start_at, "end_at": end_at},
        headers=headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert len(payload["items"]) == 1


def test_list_calls_rejects_invalid_time_range(client):
    headers = _create_call_history(client)
    response = client.get(
        "/v1/calls?start_at=2026-03-14T10:00:00Z&end_at=2026-03-13T10:00:00Z",
        headers=headers,
    )

    assert response.status_code == 422
