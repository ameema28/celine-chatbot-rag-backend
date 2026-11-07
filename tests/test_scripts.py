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
bench = _load("benchmark")


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


@pytest.mark.parametrize(
    "values, p, expected",
    [
        (list(range(1, 21)), 50, 10),
        (list(range(1, 21)), 95, 19),
        (list(range(1, 21)), 100, 20),
        ([5.0], 95, 5.0),
        ([30, 10, 20], 50, 20),
        ([], 50, None),
    ],
)
def test_benchmark_nearest_rank_percentile(values, p, expected):
    assert bench.percentile(values, p) == expected


def test_benchmark_out_path_inside_repo_is_refused():
    with pytest.raises(ValueError, match="outside the repository"):
        bench.resolve_out_path(str(bench.REPO_ROOT / "bench.json"))


def test_benchmark_default_out_path_is_outside_repo():
    path = bench.resolve_out_path(None)
    assert bench.REPO_ROOT not in path.parents
    assert path.name.startswith("celine_benchmark_")


def test_benchmark_interval_below_rate_limit_needs_force():
    assert bench.validate_interval(6.5, force=False) == 6.5
    with pytest.raises(ValueError, match="--force"):
        bench.validate_interval(2.0, force=False)
    assert bench.validate_interval(2.0, force=True) == 2.0
    with pytest.raises(ValueError):
        bench.validate_interval(-1, force=True)


def test_benchmark_summary_counts_and_stats():
    records = [
        {"status": 200, "fallback_used": False, "server_ms": 400, "client_ms": 600},
        {"status": 200, "fallback_used": False, "server_ms": 200, "client_ms": 500},
        {"status": 200, "fallback_used": True, "server_ms": 0, "client_ms": 100},
        {"status": 429, "client_ms": 50},
        {"status": None, "error": "URLError: x", "client_ms": 90000},
    ]
    summary = bench.summarize(records)
    assert summary["ok"] == 3
    assert summary["rate_limited_429"] == 1
    assert summary["errors"] == 1
    assert summary["fallback_count"] == 1
    assert summary["client_ms"] == {"count": 3, "p50": 500, "p95": 600, "max": 600}
    assert summary["server_ms_live"] == {"count": 2, "p50": 200, "p95": 400, "max": 400}
