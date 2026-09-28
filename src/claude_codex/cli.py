from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Sequence
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_MODEL = "claude-sonnet-5"
DEFAULT_MAX_TOKENS = 2048
DEFAULT_SYSTEM_PROMPT = "Responde de forma clara, útil y concisa."
API_URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"
EXIT_COMMANDS = {"/salir", "/exit", "salir", "exit"}
RESET_COMMANDS = {"/nuevo", "/reset"}


class ConfigurationError(RuntimeError):
    """Indica que falta una variable de entorno o que no es válida."""


class ClaudeAPIError(RuntimeError):
    """Indica que la API de Anthropic rechazó o no completó la solicitud."""


@dataclass(frozen=True)
class Settings:
    api_key: str
    model: str
    max_tokens: int
    system_prompt: str


def load_env_file(path: Path | None = None) -> None:
    """Carga pares CLAVE=VALOR sencillos sin sobrescribir el entorno existente."""
    env_path = path or Path.cwd() / ".env"
    if not env_path.is_file():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        if key:
            os.environ.setdefault(key, value)


def load_settings() -> Settings:
    """Carga la configuración desde .env y el entorno del proceso."""
    load_env_file()

    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not api_key or api_key == "your_api_key_here":
        raise ConfigurationError(
            "Falta ANTHROPIC_API_KEY. Copia .env.example a .env y agrega tu clave."
        )

    raw_max_tokens = os.getenv("CLAUDE_MAX_TOKENS", str(DEFAULT_MAX_TOKENS)).strip()
    try:
        max_tokens = int(raw_max_tokens)
    except ValueError as exc:
        raise ConfigurationError("CLAUDE_MAX_TOKENS debe ser un número entero.") from exc

    if max_tokens <= 0:
        raise ConfigurationError("CLAUDE_MAX_TOKENS debe ser mayor que cero.")

    return Settings(
        api_key=api_key,
        model=os.getenv("CLAUDE_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL,
        max_tokens=max_tokens,
        system_prompt=(
            os.getenv("CLAUDE_SYSTEM_PROMPT", DEFAULT_SYSTEM_PROMPT).strip()
            or DEFAULT_SYSTEM_PROMPT
        ),
    )


def extract_text(response: dict[str, Any]) -> str:
    """Extrae los bloques de texto de una respuesta de Messages API."""
    parts = [
        str(block["text"])
        for block in response.get("content", [])
        if isinstance(block, dict) and block.get("type") == "text" and block.get("text")
    ]
    return "\n".join(parts).strip()


def request_message(
    *,
    api_key: str,
    model: str,
    max_tokens: int,
    system_prompt: str,
    messages: list[dict[str, str]],
    timeout: int = 120,
) -> dict[str, Any]:
    """Llama a Messages API usando únicamente la biblioteca estándar."""
    payload = json.dumps(
        {
            "model": model,
            "max_tokens": max_tokens,
            "system": system_prompt,
            "messages": messages,
        },
        ensure_ascii=False,
    ).encode("utf-8")
    request = Request(
        API_URL,
        data=payload,
        method="POST",
        headers={
            "content-type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": API_VERSION,
        },
    )

    try:
        with urlopen(request, timeout=timeout) as response:
            raw_response = response.read().decode("utf-8")
    except HTTPError as exc:
        raw_error = exc.read().decode("utf-8", errors="replace")
        try:
            error_data = json.loads(raw_error)
            detail = error_data.get("error", {}).get("message", raw_error)
        except json.JSONDecodeError:
            detail = raw_error
        raise ClaudeAPIError(f"HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise ClaudeAPIError(f"No se pudo conectar con Anthropic: {exc.reason}") from exc

    try:
        result = json.loads(raw_response)
    except json.JSONDecodeError as exc:
        raise ClaudeAPIError("Anthropic devolvió una respuesta que no es JSON válido.") from exc
    if not isinstance(result, dict):
        raise ClaudeAPIError("Anthropic devolvió un formato de respuesta inesperado.")
    return result


MessageSender = Callable[..., dict[str, Any]]


def chat_turn(
    history: list[dict[str, str]],
    user_text: str,
    settings: Settings,
    sender: MessageSender = request_message,
) -> str:
    """Envía un turno y actualiza el historial solo si la llamada tiene éxito."""
    pending_history = [*history, {"role": "user", "content": user_text}]
    response = sender(
        api_key=settings.api_key,
        model=settings.model,
        max_tokens=settings.max_tokens,
        system_prompt=settings.system_prompt,
        messages=pending_history,
    )
    assistant_text = extract_text(response)
    if not assistant_text:
        assistant_text = "[Claude no devolvió contenido de texto.]"

    history.extend(
        [
            {"role": "user", "content": user_text},
            {"role": "assistant", "content": assistant_text},
        ]
    )
    return assistant_text


def run_interactive(
    settings: Settings,
    sender: MessageSender = request_message,
) -> int:
    history: list[dict[str, str]] = []
    print(f"Claude listo ({settings.model}).")
    print("Comandos: /nuevo borra el historial; /salir termina la sesión.\n")

    while True:
        try:
            user_text = input("Tú: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nSesión finalizada.")
            return 0

        if not user_text:
            continue
        if user_text.lower() in EXIT_COMMANDS:
            print("Sesión finalizada.")
            return 0
        if user_text.lower() in RESET_COMMANDS:
            history.clear()
            print("Historial borrado.\n")
            continue

        try:
            answer = chat_turn(history, user_text, settings, sender)
        except ClaudeAPIError as exc:
            print(f"Error de Anthropic: {exc}", file=sys.stderr)
            continue

        print(f"\nClaude: {answer}\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Conversa con Claude desde la terminal."
    )
    parser.add_argument(
        "prompt",
        nargs="*",
        help="Mensaje para una consulta única; omítelo para entrar al modo interactivo.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        settings = load_settings()
    except ConfigurationError as exc:
        print(f"Error de configuración: {exc}", file=sys.stderr)
        return 2

    if not args.prompt:
        return run_interactive(settings)

    prompt = " ".join(args.prompt).strip()
    try:
        print(chat_turn([], prompt, settings))
    except ClaudeAPIError as exc:
        print(f"Error de Anthropic: {exc}", file=sys.stderr)
        return 1
    return 0

