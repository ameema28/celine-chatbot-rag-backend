"""Retrieval evaluation for the Celine knowledge base (no LLM, no API key, no network).

Each question goes through the app's own retrieval path,
app.services.context_builder.build_turn(): language detection, the French
glossary, FAISS search, the RAG_MAX_L2_DISTANCE cutoff and the top-3 limit.
That is exactly the context /api/ai/chat and /api/ai/chat/stream would use.

Metrics over the (at most 3) ids the app returns:
- hit@1 / hit@3: an expected id is ranked first / anywhere in the top 3
- MRR@3: mean of 1/rank of the first expected id (0 if none returned)
- off-topic rejection rate: share of off-topic questions with no context at all

The questions are an author-written set, not real user traffic.

Usage:
    python scripts/eval_retrieval.py --out C:/path/outside/repo/retrieval_eval.json
"""

import argparse
import json
import sys
import tempfile
import time
from collections.abc import Callable
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA = REPO_ROOT / "data" / "eval" / "retrieval_eval.jsonl"
KB_PATH = REPO_ROOT / "data" / "salon_knowledge.json"
EXPECTED_CUTOFF = 1.20
MINIMUMS = {"on_topic": 30, "on_topic_fr": 10, "off_topic": 6, "hard": 6}


def resolve_out_path(out: str | None) -> Path:
    """Absolute output path (default: system temp dir); refuses anything inside the repository."""
    if out is None:
        out = str(Path(tempfile.gettempdir()) / f"celine_retrieval_eval_{time.strftime('%Y%m%d_%H%M%S')}.json")
    path = Path(out).resolve()
    if path == REPO_ROOT or REPO_ROOT in path.parents:
        raise ValueError(f"--out must be outside the repository ({REPO_ROOT})")
    return path


def load_items(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def kb_ids() -> set[str]:
    with open(KB_PATH, encoding="utf-8") as f:
        return {entry["id"] for entry in json.load(f)}


def validate_items(items: list[dict], known_ids: set[str]) -> list[str]:
    """Problems with the dataset (empty list = valid)."""
    errors = []
    seen_q, seen_id = set(), set()
    for item in items:
        tag = item.get("id", "?")
        if item.get("kind") not in ("on_topic", "off_topic"):
            errors.append(f"{tag}: kind must be on_topic or off_topic")
        if item.get("lang") not in ("en", "fr"):
            errors.append(f"{tag}: lang must be en or fr")
        if item.get("difficulty") not in ("normal", "hard"):
            errors.append(f"{tag}: difficulty must be normal or hard")
        if tag in seen_id:
            errors.append(f"{tag}: duplicate id")
        if item.get("q", "").strip().lower() in seen_q:
            errors.append(f"{tag}: duplicate question")
        seen_id.add(tag)
        seen_q.add(item.get("q", "").strip().lower())
        expected = item.get("expected_ids", [])
        if item.get("kind") == "on_topic" and not expected:
            errors.append(f"{tag}: on_topic item needs expected_ids")
        if item.get("kind") == "off_topic" and expected:
            errors.append(f"{tag}: off_topic item must have no expected_ids")
        errors += [f"{tag}: unknown KB id {i}" for i in expected if i not in known_ids]

    on_topic = [i for i in items if i.get("kind") == "on_topic"]
    counts = {
        "on_topic": len(on_topic),
        "on_topic_fr": sum(i.get("lang") == "fr" for i in on_topic),
        "off_topic": sum(i.get("kind") == "off_topic" for i in items),
        "hard": sum(i.get("difficulty") == "hard" for i in on_topic),
    }
    errors += [
        f"need at least {minimum} {name} items, found {counts[name]}"
        for name, minimum in MINIMUMS.items()
        if counts[name] < minimum
    ]
    return errors


def first_hit_rank(returned_ids: list[str], expected_ids: list[str]) -> int | None:
    """1-based rank of the first expected id in the returned list, or None."""
    for rank, doc_id in enumerate(returned_ids, 1):
        if doc_id in expected_ids:
            return rank
    return None


def rank_metrics(ranks: list[int | None]) -> dict:
    """hit@1, hit@3 and MRR@3 for a list of first-hit ranks (None = miss)."""
    n = len(ranks)
    if n == 0:
        return {"count": 0, "hit_at_1": None, "hit_at_3": None, "mrr_at_3": None}
    return {
        "count": n,
        "hit_at_1": round(sum(r == 1 for r in ranks) / n, 4),
        "hit_at_3": round(sum(r is not None and r <= 3 for r in ranks) / n, 4),
        "mrr_at_3": round(sum(1 / r for r in ranks if r is not None and r <= 3) / n, 4),
    }


def app_retrieve(question: str) -> tuple[list[str], str]:
    """(returned KB ids, detected language) through the app's own retrieval path."""
    from app.services.context_builder import build_turn

    turn = build_turn(question)
    return [chunk["id"] for chunk in turn.chunks], turn.lang


def evaluate(items: list[dict], retrieve: Callable[[str], tuple[list[str], str]] = app_retrieve) -> dict:
    rows = []
    for item in items:
        returned, detected = retrieve(item["q"])
        rank = first_hit_rank(returned, item["expected_ids"]) if item["kind"] == "on_topic" else None
        rows.append({**item, "returned_ids": returned, "detected_lang": detected, "rank": rank})

    on_topic = [r for r in rows if r["kind"] == "on_topic"]
    off_topic = [r for r in rows if r["kind"] == "off_topic"]
    groups = {
        "overall": on_topic,
        "en": [r for r in on_topic if r["lang"] == "en"],
        "fr": [r for r in on_topic if r["lang"] == "fr"],
        "normal": [r for r in on_topic if r["difficulty"] == "normal"],
        "hard": [r for r in on_topic if r["difficulty"] == "hard"],
    }
    rejected = [r for r in off_topic if not r["returned_ids"]]
    return {
        "metrics": {name: rank_metrics([r["rank"] for r in group]) for name, group in groups.items()},
        "off_topic": {
            "count": len(off_topic),
            "rejected": len(rejected),
            "rejection_rate": round(len(rejected) / len(off_topic), 4) if off_topic else None,
        },
        "misses": [
            {"id": r["id"], "q": r["q"], "expected_ids": r["expected_ids"], "returned_ids": r["returned_ids"]}
            for r in on_topic
            if r["rank"] is None
        ],
        "off_topic_not_rejected": [
            {"id": r["id"], "q": r["q"], "returned_ids": r["returned_ids"]} for r in off_topic if r["returned_ids"]
        ],
        "rank_2_or_3": [
            {"id": r["id"], "q": r["q"], "rank": r["rank"], "returned_ids": r["returned_ids"]}
            for r in on_topic
            if r["rank"] in (2, 3)
        ],
        "language_detection_mismatches": [
            {"id": r["id"], "q": r["q"], "labelled": r["lang"], "detected": r["detected_lang"]}
            for r in rows
            if r["lang"] != r["detected_lang"]
        ],
        "rows": rows,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data", default=str(DEFAULT_DATA), help="JSONL eval set")
    parser.add_argument("--out", help="JSON results file, outside the repository (default: system temp dir)")
    parser.add_argument(
        "--allow-other-cutoff", action="store_true", help=f"Run even if RAG_MAX_L2_DISTANCE is not {EXPECTED_CUTOFF}"
    )
    args = parser.parse_args(argv)

    try:
        out = resolve_out_path(args.out)
    except ValueError as err:
        parser.error(str(err))

    items = load_items(Path(args.data))
    errors = validate_items(items, kb_ids())
    if errors:
        for error in errors:
            print(f"DATASET ERROR: {error}")
        return 2

    sys.path.insert(0, str(REPO_ROOT))
    from app.config import settings

    cutoff = settings.RAG_MAX_L2_DISTANCE
    if cutoff != EXPECTED_CUTOFF and not args.allow_other_cutoff:
        parser.error(f"RAG_MAX_L2_DISTANCE is {cutoff}, expected {EXPECTED_CUTOFF} (pass --allow-other-cutoff)")

    result = evaluate(items)
    print(f"Cutoff RAG_MAX_L2_DISTANCE={cutoff}, embedding model={settings.EMBEDDING_MODEL_NAME}")
    print(f"{'group':<8} {'n':>3} {'hit@1':>7} {'hit@3':>7} {'MRR@3':>7}")
    for name, m in result["metrics"].items():
        print(f"{name:<8} {m['count']:>3} {m['hit_at_1']:>7.4f} {m['hit_at_3']:>7.4f} {m['mrr_at_3']:>7.4f}")
    off = result["off_topic"]
    print(f"off-topic rejection: {off['rejected']}/{off['count']} = {off['rejection_rate']:.4f}")
    for miss in result["misses"]:
        print(f"MISS {miss['id']}: {miss['q']!r} expected {miss['expected_ids']} got {miss['returned_ids']}")
    for item in result["off_topic_not_rejected"]:
        print(f"OFF-TOPIC KEPT {item['id']}: {item['q']!r} got {item['returned_ids']}")
    for item in result["language_detection_mismatches"]:
        print(f"LANG {item['id']}: labelled {item['labelled']}, detected {item['detected']}")

    payload = {
        "run_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "platform": sys.platform,
        "python": sys.version.split()[0],
        "cutoff": cutoff,
        "embedding_model": settings.EMBEDDING_MODEL_NAME,
        "data": str(Path(args.data).resolve()),
        "method": "app build_turn() retrieval (glossary + cutoff + top-3), no LLM; author-written questions",
        **result,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
