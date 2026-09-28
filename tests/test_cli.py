import json

import pytest

from claude_codex import cli
from claude_codex.cli import (
    ConfigurationError,
    Settings,
    chat_turn,
    extract_text,
    load_settings,
)


class FakeSender:
    def __init__(self) -> None:
        self.kwargs = None

    def __call__(self, **kwargs):
        self.kwargs = kwargs
        return {
            "content": [
                {"type": "thinking", "text": "oculto"},
                {"type": "text", "text": "Hola desde Claude"},
            ]
        }


class FakeHTTPResponse:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return b'{"content":[{"type":"text","text":"respuesta"}]}'


def test_extract_text_ignores_non_text_blocks():
    response = {
        "content": [
            {"type": "text", "text": "uno"},
            {"type": "tool_use", "text": "ignorar"},
            {"type": "text", "text": "dos"},
        ]
    }

    assert extract_text(response) == "uno\ndos"


def test_chat_turn_sends_and_saves_conversation():
    sender = FakeSender()
    history = []
    settings = Settings("secret", "claude-test", 256, "Sé útil")

    answer = chat_turn(history, "Hola", settings, sender)

    assert answer == "Hola desde Claude"
    assert history == [
        {"role": "user", "content": "Hola"},
        {"role": "assistant", "content": "Hola desde Claude"},
    ]
    assert sender.kwargs == {
        "api_key": "secret",
        "model": "claude-test",
        "max_tokens": 256,
        "system_prompt": "Sé útil",
        "messages": [{"role": "user", "content": "Hola"}],
    }


def test_request_message_builds_official_messages_request(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["headers"] = {key.lower(): value for key, value in request.header_items()}
        captured["body"] = json.loads(request.data.decode("utf-8"))
        captured["timeout"] = timeout
        return FakeHTTPResponse()

    monkeypatch.setattr(cli, "urlopen", fake_urlopen)

    response = cli.request_message(
        api_key="secret",
        model="claude-test",
        max_tokens=256,
        system_prompt="Sé útil",
        messages=[{"role": "user", "content": "Hola"}],
    )

    assert response["content"][0]["text"] == "respuesta"
    assert captured["url"] == "https://api.anthropic.com/v1/messages"
    assert captured["headers"]["x-api-key"] == "secret"
    assert captured["headers"]["anthropic-version"] == "2023-06-01"
    assert captured["body"]["model"] == "claude-test"
    assert captured["timeout"] == 120


def test_load_settings_rejects_missing_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr("claude_codex.cli.load_env_file", lambda: None)

    with pytest.raises(ConfigurationError, match="ANTHROPIC_API_KEY"):
        load_settings()


def test_load_settings_rejects_invalid_token_limit(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "secret")
    monkeypatch.setenv("CLAUDE_MAX_TOKENS", "muchos")
    monkeypatch.setattr("claude_codex.cli.load_env_file", lambda: None)

    with pytest.raises(ConfigurationError, match="número entero"):
        load_settings()


