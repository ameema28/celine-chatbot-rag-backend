"""Security headers on the demo page at GET /."""

import base64
import hashlib
import re

import pytest
from fastapi.testclient import TestClient

from app import main

client = TestClient(main.app)


def _sha256(text: str) -> str:
    return "'sha256-" + base64.b64encode(hashlib.sha256(text.encode("utf-8")).digest()).decode() + "'"


def test_demo_page_security_headers():
    headers = client.get("/").headers
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["x-frame-options"] == "DENY"
    assert headers["referrer-policy"] == "no-referrer"
    csp = headers["content-security-policy"]
    for directive in ("default-src 'none'", "connect-src 'self'", "frame-ancestors 'none'", "base-uri 'none'"):
        assert directive in csp
    assert "unsafe-inline" not in csp


def test_csp_hashes_match_the_served_inline_blocks():
    response = client.get("/")
    csp = response.headers["content-security-policy"]
    script = re.search(r"<script>(.*?)</script>", response.text, re.DOTALL).group(1)
    style = re.search(r"<style>(.*?)</style>", response.text, re.DOTALL).group(1)
    assert f"script-src {_sha256(script)};" in csp
    assert f"style-src {_sha256(style)};" in csp


def test_csp_hash_requires_exactly_one_block():
    with pytest.raises(RuntimeError, match="exactly one inline <script>"):
        main._csp_hash("<script>a</script><script>b</script>", "script")
