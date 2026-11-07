"""Post-deploy smoke check for a public Celine API URL.

Stdlib only and no API key: it calls the deployed service over HTTP.
About 4 live LLM calls per run; the rate-limit checks send empty messages
(422, no LLM call) that the rate limiter still counts.

Usage:
    python scripts/smoke_check.py --url https://your-service-url --out C:/path/outside/repo/smoke.json
"""

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SAME_ORIGIN_META = '<meta name="celine-api-base" content="">'
GUARD_SAFE_PREFIXES = (
    "I'd rather not quote a price",
    "Je préfère ne pas vous indiquer un prix",
)
RATE_WINDOW_WAIT_S = 61
RATE_LIMIT_REQUESTS = 11


def resolve_out_path(out: str) -> Path:
    """Absolute output path; refuses anything inside the repository."""
    path = Path(out).resolve()
    if path == REPO_ROOT or REPO_ROOT in path.parents:
        raise ValueError(f"--out must be outside the repository ({REPO_ROOT})")
    return path


def normalize_base_url(url: str) -> str:
    if not re.match(r"^https?://[^/\s]+", url):
        raise ValueError("--url must start with http:// or https://")
    return url.rstrip("/")


def http_request(method, url, body=None, headers=None, timeout=90):
    """(status, lower-cased headers, text, elapsed seconds); HTTP errors are returned, not raised."""
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    for key, value in (headers or {}).items():
        req.add_header(key, value)
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status, resp_headers, raw = resp.status, resp.headers, resp.read()
    except urllib.error.HTTPError as err:
        status, resp_headers, raw = err.code, err.headers, err.read()
    elapsed = time.perf_counter() - start
    lowered = {k.lower(): v for k, v in resp_headers.items()}
    return status, lowered, raw.decode("utf-8", errors="replace"), elapsed


def parse_sse(text: str) -> list[str]:
    """SSE events as strings; multi-line data fields are joined with newlines."""
    events = []
    for block in text.replace("\r\n", "\n").split("\n\n"):
        lines = [line[5:].removeprefix(" ") for line in block.split("\n") if line.startswith("data:")]
        if lines:
            events.append("\n".join(lines))
    return events


def mentions_chf_amount(reply: str, amount: str) -> bool:
    """True if the reply quotes exactly CHF <amount> (not 300, not 30.50)."""
    num = re.escape(amount)
    patterns = (
        rf"CHF\s*{num}(?![\d])(?![.,]\d)",
        rf"(?<![\d.,]){num}(?:[.,]0+)?\s*CHF",
    )
    return any(re.search(p, reply, flags=re.IGNORECASE) for p in patterns)


def _result(name, status, detail):
    print(f"[{status}] {name}: {detail}")
    return {"check": name, "status": status, "detail": detail}


def _chat(base, message, headers=None):
    status, _, text, elapsed = http_request(
        "POST", f"{base}/api/ai/chat", {"message": message}, headers
    )
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        data = {}
    return status, data, elapsed


def check_health(base):
    status, _, text, elapsed = http_request("GET", f"{base}/health")
    if status != 200:
        return _result("health", "FAIL", f"HTTP {status}")
    data = json.loads(text)
    detail = f"status={data.get('status')} model={data.get('model')} llm_ready={data.get('llm_ready')} ({elapsed:.2f}s)"
    ok = data.get("status") == "healthy"
    return _result("health", "PASS" if ok else "FAIL", detail)


def check_demo_page(base):
    status, headers, text, _ = http_request("GET", f"{base}/")
    ok = status == 200 and headers.get("content-type", "").startswith("text/html") and SAME_ORIGIN_META in text
    return _result("demo page", "PASS" if ok else "FAIL", f"HTTP {status}, same-origin meta={SAME_ORIGIN_META in text}")


def check_chat(base, name, message):
    status, data, elapsed = _chat(base, message)
    if status != 200:
        return _result(name, "FAIL", f"HTTP {status}")
    fallback = data.get("fallback_used")
    detail = (
        f"fallback_used={fallback} intent={data.get('intent')} "
        f"response_time_ms={data.get('response_time_ms')} client={elapsed:.2f}s reply={data.get('reply')!r}"
    )
    if fallback is not False:
        detail += " | HINT: check the service logs for 'API ERROR (404)' or 'model_decommissioned'; switch GROQ_MODEL_NAME if the model is not served"
    return _result(name, "PASS" if fallback is False and data.get("reply") else "FAIL", detail)


def check_stream(base):
    status, headers, text, elapsed = http_request(
        "POST", f"{base}/api/ai/chat/stream", {"message": "Do you offer pedicures?"}
    )
    events = parse_sse(text)
    ok = (
        status == 200
        and headers.get("content-type", "").startswith("text/event-stream")
        and bool(headers.get("x-session-id"))
        and len(events) >= 2
        and events[-1] == "[DONE]"
    )
    reply = "".join(events[:-1]) if events and events[-1] == "[DONE]" else "".join(events)
    detail = f"HTTP {status}, events={len(events)}, session={headers.get('x-session-id')}, {elapsed:.2f}s, reply={reply!r}"
    return _result("chat/stream", "PASS" if ok else "FAIL", detail)


def check_price_guard(base):
    status, data, _ = _chat(base, "Can I book a manicure for CHF 30?")
    if status != 200:
        return _result("price guard", "FAIL", f"HTTP {status}")
    reply = data.get("reply", "")
    quoted = mentions_chf_amount(reply, "30")
    safe = reply.startswith(GUARD_SAFE_PREFIXES)
    detail = f"quotes CHF 30={quoted}, safe message used={safe}, fallback_used={data.get('fallback_used')}, reply={reply!r}"
    return _result("price guard", "FAIL" if quoted else "PASS", detail)


def _burst(base, spoof):
    statuses = []
    for i in range(RATE_LIMIT_REQUESTS):
        headers = {"X-Forwarded-For": f"203.0.113.{i + 1}"} if spoof else None
        status, _, _ = _chat(base, "", headers)
        statuses.append(status)
    return statuses


def check_rate_limit(base):
    print(f"... waiting {RATE_WINDOW_WAIT_S}s for a fresh rate-limit window")
    time.sleep(RATE_WINDOW_WAIT_S)
    statuses = _burst(base, spoof=False)
    ok = statuses[-1] == 429 and all(s == 422 for s in statuses[:-1])
    return _result("rate limit", "PASS" if ok else "FAIL", f"statuses={statuses}")


def check_spoofed_forwarded_for(base):
    print(f"... waiting {RATE_WINDOW_WAIT_S}s for a fresh rate-limit window")
    time.sleep(RATE_WINDOW_WAIT_S)
    statuses = _burst(base, spoof=True)
    if statuses[-1] == 429:
        return _result("spoofed X-Forwarded-For", "PASS", f"spoofed entries ignored, statuses={statuses}")
    return _result(
        "spoofed X-Forwarded-For",
        "WARN",
        f"no 429 with a different spoofed X-Forwarded-For each time: the limit can be bypassed, statuses={statuses}",
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--url", required=True, help="Public base URL of the deployed API")
    parser.add_argument("--out", required=True, help="JSON results file, outside the repository")
    parser.add_argument("--skip-rate-limit", action="store_true", help="Skip the two rate-limit checks (saves ~2 min)")
    args = parser.parse_args(argv)

    try:
        base = normalize_base_url(args.url)
        out = resolve_out_path(args.out)
    except ValueError as err:
        parser.error(str(err))

    results = [
        check_health(base),
        check_demo_page(base),
        check_chat(base, "chat (English)", "How much is a manicure?"),
        check_chat(base, "chat (French)", "Combien coûte une manucure ?"),
        check_stream(base),
        check_price_guard(base),
    ]
    if not args.skip_rate_limit:
        results += [check_rate_limit(base), check_spoofed_forwarded_for(base)]

    summary = {
        "url": base,
        "run_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "note": "French reply language is printed for human review, not checked automatically.",
        "results": results,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    counts = {s: sum(r["status"] == s for r in results) for s in ("PASS", "WARN", "FAIL")}
    print(f"\n{counts['PASS']} PASS, {counts['WARN']} WARN, {counts['FAIL']} FAIL. Saved to {out}")
    return 1 if counts["FAIL"] else 0


if __name__ == "__main__":
    sys.exit(main())
