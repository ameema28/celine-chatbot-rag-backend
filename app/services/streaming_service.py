import logging
from collections.abc import AsyncGenerator

from app import llm
from app.price_guard import guard_reply
from app.services.context_builder import build_turn, fallback_reply, word_chunks

logger = logging.getLogger(__name__)


async def generate_streaming_rag_response(
    user_query: str,
    session_id: str = "unknown",
    history: list[dict[str, str]] | None = None,
) -> AsyncGenerator[str, None]:
    """Stream a reply using the same turn, key check, fallback and price guard as /chat.

    The LLM output is buffered and checked by the price guard before anything
    is sent, then re-streamed as word-sized chunks (SSE format unchanged).
    """
    turn = build_turn(user_query, history)

    if not llm.groq_key_usable():
        logger.warning(f"[{session_id}] No usable GROQ_API_KEY: streaming offline fallback")
        reply = fallback_reply(turn)
    else:
        try:
            client = llm.get_groq_client()
            stream = client.chat.completions.create(**llm.completion_kwargs(turn.messages, stream=True))
            parts = []
            for chunk in stream:
                content = chunk.choices[0].delta.content
                if content:
                    parts.append(content)
            reply = "".join(parts).strip()
            if not reply:
                logger.warning(f"[{session_id}] Empty model reply: streaming offline fallback")
                reply = fallback_reply(turn)
        except Exception as e:  # noqa: BLE001 - any LLM failure must degrade to the fallback
            logger.error(f"[{session_id}] Streaming error: {type(e).__name__}: {e}")
            reply = fallback_reply(turn)

    reply = guard_reply(reply, turn.computed_prices, session_id, turn.lang)
    for piece in word_chunks(reply):
        yield piece
