# Claude Codex

Cliente de terminal en Python para conversar con Claude mediante la API oficial de Anthropic. Permite consultas únicas y sesiones interactivas con historial en memoria.

La aplicación utiliza HTTPS y la biblioteca estándar de Python. No necesita el SDK de Anthropic ni dependencias externas para ejecutarse.

## Requisitos

- Python 3.10 o superior.
- Una clave de la [Consola de Anthropic](https://console.anthropic.com/).
- Crédito o facturación habilitada en Anthropic. El uso de la API se cobra por separado de cualquier suscripción a Claude.ai.

## Instalación

```powershell
git clone https://github.com/marianaedson15-lgtm/claude-codex.git
cd claude-codex
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
Copy-Item .env.example .env
```

En macOS o Linux, activa el entorno con `source .venv/bin/activate` y copia la configuración con `cp .env.example .env`.

Abre `.env` y sustituye `your_api_key_here` por tu clave. Este archivo está excluido de Git y no debe publicarse.

## Uso

En Windows, después de configurar `.env`, también puedes hacer doble clic en `Iniciar Claude.cmd`.

Inicia una conversación interactiva:

```powershell
claude-chat
```

También puedes usar el módulo directamente:

```powershell
python -m claude_codex
```

Para realizar una sola consulta:

```powershell
claude-chat "Explica qué hace este proyecto"
```

Dentro del modo interactivo:

- `/nuevo` borra el historial de la sesión.
- `/salir` termina el programa.

## Configuración

| Variable | Valor predeterminado | Uso |
| --- | --- | --- |
| `ANTHROPIC_API_KEY` | Obligatoria | Clave privada de la API. |
| `CLAUDE_MODEL` | `claude-sonnet-5` | Modelo solicitado a Anthropic. |
| `CLAUDE_MAX_TOKENS` | `2048` | Límite máximo de tokens de salida. |
| `CLAUDE_SYSTEM_PROMPT` | Respuesta clara y concisa | Instrucción general para Claude. |

Los nombres de modelo pueden cambiar o retirarse. Si el predeterminado deja de estar disponible para tu cuenta, actualiza `CLAUDE_MODEL` en `.env` con uno habilitado en la consola de Anthropic.

## Pruebas

```powershell
python -m pip install -e ".[dev]"
pytest
```

Las pruebas usan un cliente simulado: no requieren una clave ni generan cargos.

## Seguridad

- No pegues tu clave en el código, los commits, incidencias o conversaciones.
- Si una clave se publica accidentalmente, revócala inmediatamente desde la consola de Anthropic.
- El historial vive únicamente en memoria y se elimina al cerrar el programa.


