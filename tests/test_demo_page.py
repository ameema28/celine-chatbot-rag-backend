"""demo.html served at GET / with a same-origin API base."""

import json
import re
import shutil
import subprocess

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


RESPONSE_TIME_FN = re.compile(r"function formatResponseTime\(data\) \{.*?\n\s*\}", re.DOTALL)


def test_served_page_formats_response_time():
    body = client.get("/").text
    assert 'row("Response time", formatResponseTime(data))' in body
    match = RESPONSE_TIME_FN.search(body)
    assert match
    fn = match.group(0)
    assert 'if (data.fallback_used) return "n/a (offline fallback)";' in fn
    assert 'if (data.response_time_ms === 0) return "< 1 ms";' in fn
    assert "return `${data.response_time_ms} ms`;" in fn


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js not installed")
def test_response_time_format_runs_in_node():
    fn = RESPONSE_TIME_FN.search(client.get("/").text).group(0)
    script = fn + (
        "\nconsole.log(JSON.stringify(["
        "formatResponseTime({fallback_used: true, response_time_ms: 0}),"
        "formatResponseTime({fallback_used: false, response_time_ms: 0}),"
        "formatResponseTime({fallback_used: false, response_time_ms: 812})]));"
    )
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True, timeout=30)
    assert json.loads(out.stdout) == ["n/a (offline fallback)", "< 1 ms", "812 ms"]


def test_missing_meta_marker_fails_loudly(tmp_path, monkeypatch):
    page = tmp_path / "demo.html"
    page.write_text("<html><head></head></html>", encoding="utf-8")
    monkeypatch.setattr(main, "DEMO_PAGE_PATH", page)
    with pytest.raises(RuntimeError, match="celine-api-base"):
        main._load_demo_page()
