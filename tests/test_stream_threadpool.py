"""/chat/stream does its blocking work (retrieval, Groq stream) outside the event loop."""

import asyncio
import threading

from fastapi.testclient import TestClient

from app import main
from app.services import streaming_service
from tests.sse_utils import sse_text

client = TestClient(main.app)


def test_stream_reply_is_built_off_the_event_loop_thread(live_llm, monkeypatch):
    seen = {}
    real_build = streaming_service.build_stream_reply

    def spy(*args):
        seen["build_thread"] = threading.get_ident()
        return real_build(*args)

    async def loop_thread():
        return threading.get_ident()

    real_generate = streaming_service.generate_streaming_rag_response

    async def wrapped(*args):
        seen["loop_thread"] = await loop_thread()
        async for piece in real_generate(*args):
            yield piece

    monkeypatch.setattr(streaming_service, "build_stream_reply", spy)
    monkeypatch.setattr(main, "generate_streaming_rag_response", wrapped)
    body = client.post("/api/ai/chat/stream", json={"message": "How much is a manicure?"}).text
    assert sse_text(body) == live_llm.reply
    assert seen["build_thread"] != seen["loop_thread"]


def test_build_stream_reply_matches_chat_reply():
    chat_reply = client.post("/api/ai/chat", json={"message": "What nail services do you offer?"}).json()["reply"]
    assert streaming_service.build_stream_reply("What nail services do you offer?") == chat_reply


def test_async_generator_still_yields_word_chunks():
    async def collect():
        return [p async for p in streaming_service.generate_streaming_rag_response("How much is a manicure?")]

    pieces = asyncio.run(collect())
    assert len(pieces) > 1
    assert "".join(pieces) == streaming_service.build_stream_reply("How much is a manicure?")
