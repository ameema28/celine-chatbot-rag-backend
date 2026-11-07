"""Follow-up questions: retrieval may use the previous user message; the prompt never does."""

from fastapi.testclient import TestClient

from app import main
from app.services import context_builder
from app.services.context_builder import _is_follow_up, build_turn

client = TestClient(main.app)

FEET_IDS = {"srv_feet", "srv_pedicure_detail", "srv_simple_foot", "srv_foot_spa"}


def _history(question: str) -> list[dict]:
    return [
        {"role": "user", "content": question},
        {"role": "assistant", "content": "Our manicure is CHF 45."},
    ]


def _ids(turn) -> set[str]:
    return {chunk["id"] for chunk in turn.chunks}


def test_and_for_the_feet_after_manicure_question():
    turn = build_turn("and for the feet?", _history("How much is a manicure?"))
    assert FEET_IDS & _ids(turn)
    assert turn.messages[-1] == {"role": "user", "content": "and for the feet?"}
    assert turn.user_query == "and for the feet?"
    assert "How much is a manicure?" not in turn.system_prompt


def test_same_message_without_history_gets_no_context():
    assert build_turn("and for the feet?").chunks == []


def test_french_follow_up():
    turn = build_turn("et pour les pieds ?", _history("Combien coûte une manucure ?"))
    assert FEET_IDS & _ids(turn)
    assert turn.lang == "fr"


def test_message_with_own_match_ignores_previous_message(monkeypatch):
    seen: list[list[str]] = []
    real_search = context_builder._search
    monkeypatch.setattr(context_builder, "_search", lambda queries: seen.append(queries) or real_search(queries))
    turn = build_turn("What are your opening hours?", _history("How much is a manicure?"))
    assert len(seen) == 1
    assert _ids(turn) == {"salon_hours"}


def test_off_topic_question_in_a_session_still_gets_no_context():
    history = _history("Do you do eyelash extensions?")
    for question in ["What is the weather tomorrow?", "Can you recommend a good pizza restaurant?"]:
        assert build_turn(question, history).chunks == []


def test_new_self_contained_question_is_not_combined():
    assert build_turn("Where are you located?", _history("How much is a manicure?")).chunks == []


def test_follow_up_trigger():
    assert _is_follow_up("and for the feet?")
    assert _is_follow_up("the feet?")
    assert _is_follow_up("is it expensive?")
    assert _is_follow_up("Et pour ça, combien de temps ?")
    assert _is_follow_up("what about for my legs please?")
    assert not _is_follow_up("What is the weather tomorrow?")
    assert not _is_follow_up("Where are you located?")
    assert not _is_follow_up("")


def test_follow_up_through_the_api_keeps_the_real_message(live_llm):
    first = client.post("/api/ai/chat", json={"message": "How much is a manicure?"}).json()
    second = client.post(
        "/api/ai/chat", json={"message": "and for the feet?", "session_id": first["session_id"]}
    ).json()
    assert FEET_IDS & {chunk["id"] for chunk in second["retrieved_context"]}
    assert live_llm.calls[-1]["messages"][-1] == {"role": "user", "content": "and for the feet?"}
