"""Sequential /api/ai/chat latency benchmark against a public URL.

Stdlib only and no API key: it calls the deployed service over HTTP.
One warm-up request (excluded from the stats), then N sequential requests,
each in a new session. Requests are paced (default 6.5 s start to start) so a
single client stays under the API's 10 requests/minute limit.

Client times include the network between you and the service.
Percentiles use the nearest-rank method (p95 of 20 values is the 19th).

Usage:
    python scripts/benchmark.py --url https://your-service-url -n 20 --out C:/path/outside/repo/bench.json
"""

import argparse
import json
import math
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MIN_INTERVAL_S = 6.1
QUESTIONS = (
    "How much is a manicure?",
    "Combien coûte une pédicure ?",
    "Do you offer eyelash extensions?",
    "Proposez-vous l'épilation des sourcils ?",
)


def resolve_out_path(out: str | None) -> Path:
    """Absolute output path (default: system temp dir); refuses anything inside the repository."""
    if out is None:
        out = str(Path(tempfile.gettempdir()) / f"celine_benchmark_{time.strftime('%Y%m%d_%H%M%S')}.json")
    path = Path(out).resolve()
    if path == REPO_ROOT or REPO_ROOT in path.parents:
        raise ValueError(f"--out must be outside the repository ({REPO_ROOT})")
    return path


def validate_interval(interval: float, force: bool) -> float:
    if interval < 0:
        raise ValueError("--interval must be >= 0")
    if interval < MIN_INTERVAL_S and not force:
        raise ValueError(
            f"--interval below {MIN_INTERVAL_S}s would exceed 10 requests/minute; pass --force to override"
        )
    return interval


def percentile(values: list[float], p: float) -> float | None:
    """Nearest-rank percentile; None for an empty list."""
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, math.ceil(p / 100 * len(ordered)))
    return ordered[rank - 1]


def stats(values: list[float]) -> dict:
    return {
        "count": len(values),
        "p50": percentile(values, 50),
        "p95": percentile(values, 95),
        "max": max(values) if values else None,
    }


def one_request(base: str, message: str, timeout: float) -> dict:
    data = json.dumps({"message": message}).encode("utf-8")
    req = urllib.request.Request(
        f"{base}/api/ai/chat", data=data, method="POST", headers={"Content-Type": "application/json"}
    )
    start = time.perf_counter()
    record = {"message": message}
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            record.update(
                status=resp.status,
                fallback_used=body.get("fallback_used"),
                server_ms=body.get("response_time_ms"),
            )
    except urllib.error.HTTPError as err:
        record.update(status=err.code)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as err:
        record.update(status=None, error=f"{type(err).__name__}: {err}")
    record["client_ms"] = round((time.perf_counter() - start) * 1000)
    return record


def summarize(records: list[dict]) -> dict:
    ok = [r for r in records if r.get("status") == 200]
    live = [r for r in ok if r.get("fallback_used") is False]
    return {
        "requests": len(records),
        "ok": len(ok),
        "rate_limited_429": sum(r.get("status") == 429 for r in records),
        "errors": sum(r.get("status") not in (200, 429) for r in records),
        "fallback_count": sum(r.get("fallback_used") is True for r in ok),
        "client_ms": stats([r["client_ms"] for r in ok]),
        "server_ms_live": stats([r["server_ms"] for r in live if isinstance(r.get("server_ms"), int)]),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--url", required=True, help="Public base URL of the deployed API")
    parser.add_argument("-n", type=int, default=20, help="Measured requests (default 20)")
    parser.add_argument("--interval", type=float, default=6.5, help="Seconds between request starts (default 6.5)")
    parser.add_argument("--force", action="store_true", help=f"Allow --interval below {MIN_INTERVAL_S}s")
    parser.add_argument("--timeout", type=float, default=90, help="Per-request timeout in seconds")
    parser.add_argument("--out", help="JSON results file, outside the repository (default: system temp dir)")
    args = parser.parse_args(argv)

    try:
        if args.n < 1:
            raise ValueError("-n must be >= 1")
        if not args.url.startswith(("http://", "https://")):
            raise ValueError("--url must start with http:// or https://")
        interval = validate_interval(args.interval, args.force)
        out = resolve_out_path(args.out)
    except ValueError as err:
        parser.error(str(err))
    base = args.url.rstrip("/")

    print(f"Warm-up request to {base} (excluded from stats)")
    warmup = one_request(base, QUESTIONS[0], args.timeout)
    print(f"  warm-up: status={warmup.get('status')} client_ms={warmup['client_ms']}")

    records = []
    next_start = time.perf_counter() + interval
    for i in range(args.n):
        delay = next_start - time.perf_counter()
        if delay > 0:
            time.sleep(delay)
        next_start = time.perf_counter() + interval
        record = one_request(base, QUESTIONS[i % len(QUESTIONS)], args.timeout)
        records.append(record)
        print(
            f"  {i + 1:>2}/{args.n}: status={record.get('status')} client_ms={record['client_ms']} "
            f"server_ms={record.get('server_ms')} fallback={record.get('fallback_used')}"
        )

    summary = summarize(records)
    client, server = summary["client_ms"], summary["server_ms_live"]
    print(
        f"\nClient end-to-end ms (includes your network), {client['count']} OK: "
        f"p50={client['p50']} p95={client['p95']} max={client['max']}"
    )
    print(f"Server LLM ms (response_time_ms, live only): p50={server['p50']} p95={server['p95']} max={server['max']}")
    print(
        f"Fallbacks: {summary['fallback_count']}, 429s: {summary['rate_limited_429']}, "
        f"errors: {summary['errors']}"
    )

    result = {
        "url": base,
        "run_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "n": args.n,
        "interval_s": interval,
        "method": "sequential, new session per request, nearest-rank percentiles, warm-up excluded",
        "warmup": warmup,
        "summary": summary,
        "requests": records,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved to {out}")
    if summary["ok"] != args.n:
        print("Not every measured request returned 200; the numbers above are incomplete.")
        if summary["rate_limited_429"]:
            print("Got 429s: wait 60 s after other scripts before benchmarking, or increase --interval.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
