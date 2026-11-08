import logging
import time

from groq import APIConnectionError, APIError, AuthenticationError

from app import llm
from app.config import settings
from app.price_guard import guard_reply
from app.services.context_builder import build_turn, fallback_reply

logger = logging.getLogger(__name__)


def generate_rag_response(
    user_query: str,
    session_id: str = "unknown",
    history: list[dict[str, str]] | None = None,
) -> dict:
    turn = build_turn(user_query, history)

    ai_reply = ""
    fallback_used = False
    response_time_ms = 0

    key_status = llm.key_status()
    if key_status != "ok":
        logger.warning(f"[{session_id}] No usable GROQ_API_KEY ({key_status}): offline fallback")
        fallback_used = True
    else:
        try:
            start_time = time.time()
            logger.info(f"[{session_id}] Calling Groq: {settings.GROQ_MODEL_NAME}")
            client = llm.get_groq_client()
            completion = client.chat.completions.create(**llm.completion_kwargs(turn.messages))
            choice = completion.choices[0]
            ai_reply = (choice.message.content or "").strip()
            response_time_ms = int((time.time() - start_time) * 1000)
            finish_reason = getattr(choice, "finish_reason", None)
            if not ai_reply:
                # e.g. the token budget was used up by reasoning: no answer text.
                logger.warning(f"[{session_id}] Empty model reply (finish_reason={finish_reason})")
                fallback_used = True
                response_time_ms = 0
            else:
                logger.info(f"[{session_id}] Groq success in {response_time_ms}ms")
                if finish_reason == "length":
                    logger.warning(f"[{session_id}] Model reply cut at the token limit")

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

    ai_reply = guard_reply(ai_reply, turn.computed_prices, session_id, turn.lang)

    return {
        "reply": ai_reply,
        "intent": turn.intent,
        "retrieved_context": turn.chunks,
        "fallback_used": fallback_used,
        "response_time_ms": response_time_ms,
    }
