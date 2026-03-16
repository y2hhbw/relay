from pathlib import Path


def test_landing_page_contains_primary_github_cta():
    page = Path("site/index.html")

    assert page.exists()

    html = page.read_text(encoding="utf-8")

    assert "https://github.com/y2hhbw/relay" in html
    assert "Star on GitHub" in html
    assert "buy its own tokens" in html
