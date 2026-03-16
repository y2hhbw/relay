import httpx

from app.providers.search import SearchProviderError, search_web


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self):
        return self._payload


def test_duckduckgo_mode_parses_response(monkeypatch):
    def fake_get(*args, **kwargs):
        del args
        del kwargs
        return _FakeResponse(
            {
                "Heading": "Relay",
                "AbstractURL": "https://relay.example",
                "Abstract": "Billing gateway",
            }
        )

    monkeypatch.setattr(httpx, "get", fake_get)

    result = search_web("relay", provider_mode="duckduckgo", timeout_seconds=1.0)

    assert result == {
        "results": [
            {
                "title": "Relay",
                "url": "https://relay.example",
                "snippet": "Billing gateway",
            }
        ]
    }


def test_duckduckgo_mode_maps_http_errors(monkeypatch):
    def fake_get(*args, **kwargs):
        del args
        del kwargs
        raise httpx.ConnectError("boom")

    monkeypatch.setattr(httpx, "get", fake_get)

    try:
        search_web("relay", provider_mode="duckduckgo", timeout_seconds=1.0)
    except SearchProviderError:
        assert True
    else:
        assert False
