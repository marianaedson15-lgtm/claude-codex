from types import SimpleNamespace

import pytest

from claude_codex.cli import (
    ConfigurationError,
    Settings,
    chat_turn,
    extract_text,
    load_settings,
)


class FakeMessages:
    def __init__(self) -> None:
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(
            content=[
                SimpleNamespace(type="thinking", text="oculto"),
                SimpleNamespace(type="text", text="Hola desde Claude"),
            ]
        )


class FakeClient:
    def __init__(self) -> None:
        self.messages = FakeMessages()


def test_extract_text_ignores_non_text_blocks():
    response = SimpleNamespace(
        content=[
            SimpleNamespace(type="text", text="uno"),
            SimpleNamespace(type="tool_use", text="ignorar"),
            SimpleNamespace(type="text", text="dos"),
        ]
    )

    assert extract_text(response) == "uno\ndos"


def test_chat_turn_sends_and_saves_conversation():
    client = FakeClient()
    history = []
    settings = Settings("secret", "claude-test", 256, "Sé útil")

    answer = chat_turn(client, history, "Hola", settings)

    assert answer == "Hola desde Claude"
    assert history == [
        {"role": "user", "content": "Hola"},
        {"role": "assistant", "content": "Hola desde Claude"},
    ]
    assert client.messages.kwargs == {
        "model": "claude-test",
        "max_tokens": 256,
        "system": "Sé útil",
        "messages": [{"role": "user", "content": "Hola"}],
    }


def test_load_settings_rejects_missing_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr("claude_codex.cli.load_dotenv", lambda: None)

    with pytest.raises(ConfigurationError, match="ANTHROPIC_API_KEY"):
        load_settings()


def test_load_settings_rejects_invalid_token_limit(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "secret")
    monkeypatch.setenv("CLAUDE_MAX_TOKENS", "muchos")
    monkeypatch.setattr("claude_codex.cli.load_dotenv", lambda: None)

    with pytest.raises(ConfigurationError, match="número entero"):
        load_settings()

