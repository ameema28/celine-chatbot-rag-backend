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


def test_openapi_has_no_contact_email():
    schema = client.get("/openapi.json")
    assert "email" not in schema.json()["info"].get("contact", {})
    assert "@" not in schema.text.split('"paths"')[0]


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


def test_french_example_buttons_are_marked_french():
    body = client.get("/").text
    assert body.count('data-lang="fr" lang="fr"') == 2


def test_status_line_uses_plain_words_not_model_or_version():
    body = client.get("/").text
    assert "data.llm_ready" in body
    assert "data.model" not in body
    assert "data.version" not in body


def test_visitor_error_messages_are_friendly():
    body = client.get("/").text
    assert "if (status === 429)" in body
    assert "Please wait a minute and try again." in body
    assert "something went wrong on our side" in body
    # A non-JSON error body (e.g. a proxy 502 page) must not look like a network failure.
    assert "try { data = await response.json(); } catch (e)" in body
    assert "Could not connect to AI service" not in body


def test_mobile_layout_rules_present():
    body = client.get("/").text
    assert "height: 100dvh;" in body
    assert "flex-wrap: nowrap; overflow-x: auto;" in body
    assert "@media (max-width: 600px), (max-height: 640px)" in body
    assert "min-height: 300px" not in body


def test_newest_reply_start_is_kept_in_view():
    body = client.get("/").text
    assert "node.offsetHeight > chatBox.clientHeight ? node.offsetTop : chatBox.scrollHeight" in body
    assert 'window.visualViewport.addEventListener("resize", keepNewestVisible)' in body


def test_missing_meta_marker_fails_loudly(tmp_path, monkeypatch):
    page = tmp_path / "demo.html"
    page.write_text("<html><head></head></html>", encoding="utf-8")
    monkeypatch.setattr(main, "DEMO_PAGE_PATH", page)
    with pytest.raises(RuntimeError, match="celine-api-base"):
        main._load_demo_page()
