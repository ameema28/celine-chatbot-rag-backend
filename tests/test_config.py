"""Settings: environment variables take precedence over the .env file."""

from app.config import Settings


def test_env_var_overrides_env_file(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("GROQ_API_KEY=from-dot-env-placeholder\nGROQ_MODEL_NAME=file-model\n", encoding="utf-8")
    monkeypatch.setenv("GROQ_API_KEY", "from-environment-placeholder")
    monkeypatch.delenv("GROQ_MODEL_NAME", raising=False)
    loaded = Settings(_env_file=env_file)
    assert loaded.GROQ_API_KEY == "from-environment-placeholder"
    assert loaded.GROQ_MODEL_NAME == "file-model"
