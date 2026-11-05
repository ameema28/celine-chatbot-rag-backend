import logging
import time

from groq import APIConnectionError, APIError, AuthenticationError

from app import llm
from app.config import settings
from app.services.context_builder import build_turn, fallback_reply

logger = logging.getLogger(__name__)
GROQ_MODEL = settings.GROQ_MODEL_NAME


def generate_rag_response(
    user_query: str,
    session_id: str = "unknown",
    history: list[dict[str, str]] | None = None,
) -> dict:
    turn = build_turn(user_query, history)

    ai_reply = ""
    fallback_used = False
    response_time_ms = 0

    if not settings.GROQ_API_KEY:
        logger.error(f"[{session_id}] GROQ_API_KEY missing")
        fallback_used = True
    elif not llm.groq_key_usable():
        logger.warning(f"[{session_id}] GROQ_API_KEY appears to be a placeholder")
        fallback_used = True
    else:
        try:
            start_time = time.time()
            logger.info(f"[{session_id}] Calling Groq: {GROQ_MODEL}")
            client = llm.get_groq_client()
            completion = client.chat.completions.create(
                model=GROQ_MODEL,
                messages=turn.messages,
                temperature=0.3,
                max_tokens=200,
            )
            ai_reply = completion.choices[0].message.content
            response_time_ms = int((time.time() - start_time) * 1000)
            logger.info(f"[{session_id}] Groq success in {response_time_ms}ms")

            if response_time_ms > 4000:
                logger.warning(f"[{session_id}] SLOW: {response_time_ms}ms > 4s target")

        except AuthenticationError as e:
            logger.error(f"[{session_id}] AUTH ERROR: {e}")
            fallback_used = True
        except APIConnectionError as e:
            logger.error(f"[{session_id}] CONNECTION ERROR: {e}")
            fallback_used = True
        except APIError as e:
            status = getattr(e, "status_code", "unknown")
            logger.error(f"[{session_id}] API ERROR ({status}): {e}")
            fallback_used = True
        except Exception as e:  # noqa: BLE001 - any LLM failure must degrade to the fallback
            logger.error(f"[{session_id}] UNEXPECTED: {type(e).__name__}: {e}")
            fallback_used = True

    if fallback_used:
        ai_reply = fallback_reply(turn)

    return {
        "reply": ai_reply,
        "intent": turn.intent,
        "retrieved_context": turn.chunks,
        "fallback_used": fallback_used,
        "response_time_ms": response_time_ms,
    }
