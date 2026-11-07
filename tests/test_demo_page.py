"""demo.html served at GET / with a same-origin API base."""

import pytest
from fastapi.testclient import TestClient

from app import main

client = TestClient(main.app)


def test_root_serves_demo_html():
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "Celine Esthetique - AI Concierge" in response.text


def test_served_page_uses_same_origin_api_base():
    body = client.get("/").text
    assert main.DEMO_SAME_ORIGIN_META in body
    assert main.DEMO_LOCAL_API_META not in body


def test_demo_file_keeps_localhost_default_for_local_use():
    raw = main.DEMO_PAGE_PATH.read_text(encoding="utf-8")
    assert main.DEMO_LOCAL_API_META in raw
    assert "?api=" in raw


def test_root_is_not_rate_limited():
    for _ in range(12):
        assert client.get("/").status_code == 200


def test_root_not_in_openapi_schema():
    assert "/" not in client.get("/openapi.json").json()["paths"]


def test_served_page_has_two_english_and_two_french_example_buttons():
    body = client.get("/").text
    assert body.count('class="example-btn" data-lang="en"') == 2
    assert body.count('class="example-btn" data-lang="fr"') == 2


def test_served_page_has_typing_indicator_and_details_toggle():
    body = client.get("/").text
    assert "showTyping" in body
    assert 'summary.textContent = "Show details"' in body


def test_details_toggle_uses_only_fields_the_api_returns():
    body = client.get("/").text
    used = {"intent", "fallback_used", "response_time_ms", "retrieved_context"}
    for field in used:
        assert f"data.{field}" in body
    assert used <= set(main.ChatResponse.model_fields)


def test_missing_meta_marker_fails_loudly(tmp_path, monkeypatch):
    page = tmp_path / "demo.html"
    page.write_text("<html><head></head></html>", encoding="utf-8")
    monkeypatch.setattr(main, "DEMO_PAGE_PATH", page)
    with pytest.raises(RuntimeError, match="celine-api-base"):
        main._load_demo_page()
