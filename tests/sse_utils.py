"""Helpers to read Server-Sent Events bodies in tests."""


def sse_events(body: str) -> list[str]:
    """Return each event's data, joining multi-line data with newlines (SSE spec)."""
    events = []
    for raw in body.split("\n\n"):
        lines = [line[6:] if line.startswith("data: ") else line[5:]
                 for line in raw.split("\n") if line.startswith("data:")]
        if lines:
            events.append("\n".join(lines))
    return events


def sse_text(body: str) -> str:
    """Concatenate all data events except the final [DONE] marker."""
    events = sse_events(body)
    assert events and events[-1] == "[DONE]", "stream must end with [DONE]"
    return "".join(events[:-1])
