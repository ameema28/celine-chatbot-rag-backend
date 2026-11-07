"""Retrieval evaluation: metric helpers, dataset checks and a regression gate.

The gate runs the whole eval set through the app's own retrieval path
(build_turn: French glossary, FAISS, cutoff, top-3). No LLM is involved.
Thresholds are measured values: first set on 2026-11-07 (identical on Windows
venv and Linux python:3.11-slim image); overall, fr and hard raised to the values
re-measured on 2026-11-08 (Windows venv only). Thresholds are only ever raised.
Any drop fails the test.
"""

import importlib.util
from pathlib import Path

import pytest

from app.config import settings

_SPEC = importlib.util.spec_from_file_location(
    "scripts_eval_retrieval", Path(__file__).resolve().parent.parent / "scripts" / "eval_retrieval.py"
)
ev = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(ev)

MEASURED = {
    "overall": {"hit_at_1": 0.8511, "hit_at_3": 0.9149, "mrr_at_3": 0.8830},
    "en": {"hit_at_1": 0.7742, "hit_at_3": 0.8710, "mrr_at_3": 0.8226},
    "fr": {"hit_at_1": 1.0000, "hit_at_3": 1.0000, "mrr_at_3": 1.0000},
    "normal": {"hit_at_1": 0.8947, "hit_at_3": 0.9474, "mrr_at_3": 0.9211},
    "hard": {"hit_at_1": 0.6667, "hit_at_3": 0.7778, "mrr_at_3": 0.7222},
}
MEASURED_OFF_TOPIC_REJECTION = 1.0


@pytest.fixture(scope="module")
def items():
    return ev.load_items(ev.DEFAULT_DATA)


def test_first_hit_rank():
    assert ev.first_hit_rank(["a", "b", "c"], ["b"]) == 2
    assert ev.first_hit_rank(["a", "b", "c"], ["c", "a"]) == 1
    assert ev.first_hit_rank(["a"], ["z"]) is None
    assert ev.first_hit_rank([], ["a"]) is None


def test_rank_metrics():
    m = ev.rank_metrics([1, 2, None, 3])
    assert m == {"count": 4, "hit_at_1": 0.25, "hit_at_3": 0.75, "mrr_at_3": round((1 + 1 / 2 + 1 / 3) / 4, 4)}
    assert ev.rank_metrics([])["hit_at_1"] is None


def test_evaluate_with_fake_retriever():
    items = [
        {"id": "a", "kind": "on_topic", "lang": "en", "difficulty": "normal", "q": "x", "expected_ids": ["k1"]},
        {"id": "b", "kind": "on_topic", "lang": "fr", "difficulty": "hard", "q": "y", "expected_ids": ["k2"]},
        {"id": "c", "kind": "off_topic", "lang": "en", "difficulty": "normal", "q": "z", "expected_ids": []},
    ]
    answers = {"x": (["k1"], "en"), "y": (["k9", "k2"], "fr"), "z": (["k3"], "en")}
    result = ev.evaluate(items, retrieve=lambda q: answers[q])
    assert result["metrics"]["overall"] == {"count": 2, "hit_at_1": 0.5, "hit_at_3": 1.0, "mrr_at_3": 0.75}
    assert result["metrics"]["hard"]["mrr_at_3"] == 0.5
    assert result["off_topic"] == {"count": 1, "rejected": 0, "rejection_rate": 0.0}
    assert [r["id"] for r in result["off_topic_not_rejected"]] == ["c"]


def test_out_path_inside_repo_is_refused():
    with pytest.raises(ValueError, match="outside the repository"):
        ev.resolve_out_path(str(ev.REPO_ROOT / "eval.json"))


def test_dataset_is_valid(items):
    assert ev.validate_items(items, ev.kb_ids()) == []


def test_validation_catches_bad_items():
    bad = [{"id": "x", "kind": "on_topic", "lang": "de", "difficulty": "normal", "q": "q", "expected_ids": ["nope"]}]
    errors = ev.validate_items(bad, {"salon_hours"})
    assert any("lang" in e for e in errors)
    assert any("unknown KB id nope" in e for e in errors)
    assert any("at least 30 on_topic" in e for e in errors)


def test_retrieval_does_not_regress(items):
    assert settings.RAG_MAX_L2_DISTANCE == ev.EXPECTED_CUTOFF
    result = ev.evaluate(items)
    for group, floors in MEASURED.items():
        for metric, floor in floors.items():
            assert result["metrics"][group][metric] >= floor, (group, metric, result["metrics"][group], result["misses"])
    assert result["off_topic"]["rejection_rate"] >= MEASURED_OFF_TOPIC_REJECTION, result["off_topic_not_rejected"]
