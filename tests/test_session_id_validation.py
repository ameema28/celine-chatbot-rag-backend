"""session_id is limited to 64 letters, digits, '-' and '_' (it is logged and stored)."""

import pytest
from fastapi.testclient import TestClient

from app import main

client = TestClient(main.app)


@pytest.mark.parametrize("path", ["/api/ai/chat", "/api/ai/chat/stream"])
@pytest.mark.parametrize("bad", ["a\nFAKE LOG LINE", "x" * 65, "", "id with spaces", "../etc", "é"])
def test_bad_session_id_is_rejected(path, bad):
    response = client.post(path, json={"message": "hello", "session_id": bad})
    assert response.status_code == 422


def test_generated_session_id_is_accepted_back():
    first = client.post("/api/ai/chat", json={"message": "How much is a manicure?"}).json()
    second = client.post("/api/ai/chat", json={"message": "and a pedicure?", "session_id": first["session_id"]})
    assert second.status_code == 200
    assert second.json()["session_id"] == first["session_id"]


def test_custom_session_id_within_rules_is_accepted():
    response = client.post("/api/ai/chat", json={"message": "hello", "session_id": "My_Session-01" + "x" * 51})
    assert response.status_code == 200
