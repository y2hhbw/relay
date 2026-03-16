from app.services.rate_limit import InMemoryRateLimiter


def test_limiter_resets_after_window():
    limiter = InMemoryRateLimiter(limit=2, window_seconds=60)

    assert limiter.check("acc_1", "search.web", now=100.0)
    assert limiter.check("acc_1", "search.web", now=110.0)
    assert not limiter.check("acc_1", "search.web", now=120.0)
    assert limiter.check("acc_1", "search.web", now=170.1)


def test_limiter_is_scoped_per_account_and_service():
    limiter = InMemoryRateLimiter(limit=1, window_seconds=60)

    assert limiter.check("acc_1", "search.web", now=100.0)
    assert not limiter.check("acc_1", "search.web", now=100.1)
    assert limiter.check("acc_1", "ocr.parse_image", now=100.1)
    assert limiter.check("acc_2", "search.web", now=100.1)
