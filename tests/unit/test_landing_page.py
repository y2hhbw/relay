from pathlib import Path


def test_landing_page_contains_bilingual_thesis_and_github_cta():
    page = Path("site/index.html")

    assert page.exists()

    html = page.read_text(encoding="utf-8")

    assert "https://github.com/y2hhbw/relay" in html
    assert "Read the thesis" in html
    assert "Agents are becoming economic actors." in html
    assert "智能体正在成为经济行为体。" in html
    assert "The missing layer is financial autonomy." in html
    assert "缺的不是更多推理，而是财务自主权。" in html
