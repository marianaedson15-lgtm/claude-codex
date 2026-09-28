from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from typing import Any, Sequence

from dotenv import load_dotenv


DEFAULT_MODEL = "claude-sonnet-5"
DEFAULT_MAX_TOKENS = 2048
DEFAULT_SYSTEM_PROMPT = "Responde de forma clara, útil y concisa."
EXIT_COMMANDS = {"/salir", "/exit", "salir", "exit"}
RESET_COMMANDS = {"/nuevo", "/reset"}


class ConfigurationError(RuntimeError):
    """Indica que falta una variable de entorno o que no es válida."""


@dataclass(frozen=True)
class Settings:
    api_key: str
    model: str
    max_tokens: int
    system_prompt: str


def load_settings() -> Settings:
    """Carga la configuración desde .env y el entorno del proceso."""
    load_dotenv()

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


def extract_text(response: Any) -> str:
    """Extrae los bloques de texto de una respuesta de Messages API."""
    parts = [
        block.text
        for block in getattr(response, "content", [])
        if getattr(block, "type", None) == "text" and getattr(block, "text", "")
    ]
    return "\n".join(parts).strip()


def chat_turn(
    client: Any,
    history: list[dict[str, str]],
    user_text: str,
    settings: Settings,
) -> str:
    """Envía un turno y actualiza el historial solo si la llamada tiene éxito."""
    pending_history = [*history, {"role": "user", "content": user_text}]
    response = client.messages.create(
        model=settings.model,
        max_tokens=settings.max_tokens,
        system=settings.system_prompt,
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
    client: Any,
    settings: Settings,
    api_error_type: type[Exception],
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
            answer = chat_turn(client, history, user_text, settings)
        except api_error_type as exc:
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

    try:
        from anthropic import APIError, Anthropic
    except ImportError as exc:
        print(
            "No se pudo cargar el SDK de Anthropic. Reinstala las dependencias "
            f"con 'python -m pip install -e .'. Detalle: {exc}",
            file=sys.stderr,
        )
        return 3

    client = Anthropic(api_key=settings.api_key)
    if not args.prompt:
        return run_interactive(client, settings, APIError)

    prompt = " ".join(args.prompt).strip()
    try:
        print(chat_turn(client, [], prompt, settings))
    except APIError as exc:
        print(f"Error de Anthropic: {exc}", file=sys.stderr)
        return 1
    return 0

