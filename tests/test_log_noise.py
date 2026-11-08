"""No tqdm progress bars or print() output in the service logs."""

import logging

from app import main
from app.database import vector_db


def test_query_encoding_disables_progress_bar(monkeypatch):
    calls = []
    real_encode = vector_db.encoder.encode

    def spy(*args, **kwargs):
        calls.append(kwargs)
        return real_encode(*args, **kwargs)

    monkeypatch.setattr(vector_db.encoder, "encode", spy)
    vector_db.search_with_scores("How much is a manicure?")
    assert calls and all(kw.get("show_progress_bar") is False for kw in calls)


def test_search_writes_nothing_to_stdout_or_stderr(capfd):
    capfd.readouterr()
    vector_db.search_context("How much is a manicure?")
    out, err = capfd.readouterr()
    assert out == ""
    assert "Batches" not in err


def test_startup_logs_index_size(caplog):
    with caplog.at_level(logging.INFO, logger="app.main"):
        main._startup_tasks()
    assert f"FAISS index: {vector_db.index.ntotal} knowledge base entries" in caplog.text
