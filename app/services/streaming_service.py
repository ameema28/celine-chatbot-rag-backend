import logging
from collections.abc import AsyncGenerator

from app import llm
from app.config import settings
from app.services.context_builder import PHONE, build_turn, fallback_reply, word_chunks

logger = logging.getLogger(__name__)
GROQ_MODEL = settings.GROQ_MODEL_NAME


async def generate_streaming_rag_response(
    user_query: str,
    session_id: str = "unknown",
    history: list[dict[str, str]] | None = None,
) -> AsyncGenerator[str, None]:
    """Stream a reply using the same turn, key check and fallback as /chat."""
    turn = build_turn(user_query, history)

    if not llm.groq_key_usable():
        logger.warning(f"[{session_id}] No usable GROQ_API_KEY: streaming offline fallback")
        for piece in word_chunks(fallback_reply(turn)):
            yield piece
        return

    sent_any = False
    try:
        client = llm.get_groq_client()
        stream = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=turn.messages,
            temperature=0.3,
            max_tokens=200,
            stream=True,
        )
        for chunk in stream:
            content = chunk.choices[0].delta.content
            if content:
                sent_any = True
                yield content
    except Exception as e:  # noqa: BLE001 - any LLM failure must degrade to the fallback
        logger.error(f"[{session_id}] Streaming error: {type(e).__name__}: {e}")
        if not sent_any:
            for piece in word_chunks(fallback_reply(turn)):
                yield piece
        else:
            yield f" For anything else, please call us at {PHONE}."
