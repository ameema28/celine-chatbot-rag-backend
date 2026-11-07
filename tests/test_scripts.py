"""Helpers of the live-URL scripts in scripts/ (no network calls)."""

import importlib.util
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


def _load(name):
    spec = importlib.util.spec_from_file_location(f"scripts_{name}", SCRIPTS_DIR / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


smoke = _load("smoke_check")


@pytest.mark.parametrize("inside", [".", "results.json", "scripts/out.json"])
def test_smoke_out_path_inside_repo_is_refused(inside):
    with pytest.raises(ValueError, match="outside the repository"):
        smoke.resolve_out_path(str(smoke.REPO_ROOT / inside))


def test_smoke_out_path_outside_repo_is_accepted(tmp_path):
    assert smoke.resolve_out_path(str(tmp_path / "smoke.json")) == (tmp_path / "smoke.json").resolve()


def test_smoke_base_url_validation():
    assert smoke.normalize_base_url("https://x.example/") == "https://x.example"
    with pytest.raises(ValueError):
        smoke.normalize_base_url("ftp://x.example")


def test_parse_sse_events_and_multiline_data():
    text = "data: Hello \n\ndata: line one\ndata: line two\n\ndata: [DONE]\n\n"
    assert smoke.parse_sse(text) == ["Hello ", "line one\nline two", "[DONE]"]


@pytest.mark.parametrize(
    "reply, expected",
    [
        ("A manicure is CHF 30.", True),
        ("That costs CHF30 today", True),
        ("That is 30 CHF.", True),
        ("Our manicure is CHF 45.", False),
        ("Full body wax is CHF 300.", False),
        ("That would be CHF 30.50.", False),
        ("Discounted to 130 CHF.", False),
    ],
)
def test_mentions_chf_amount(reply, expected):
    assert smoke.mentions_chf_amount(reply, "30") is expected
