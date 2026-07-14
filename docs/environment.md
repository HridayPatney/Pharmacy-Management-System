# Environment variables

PharmaAssist loads configuration from the process environment and optionally from a local `.env` file (via `python-dotenv`).

## Variables

| Name | Required | Default | Purpose |
|------|----------|---------|---------|
| `GEMINI_API_KEY` | Yes for OCR | _(none)_ | Google Gemini API key used by `POST /ocr/extract` |
| `CORS_ORIGINS` | No | `http://localhost:8501` | Comma-separated allowed origins for the FastAPI CORS middleware |

## Local setup

1. Copy `.env.example` to `.env` in the repository root.
2. Set `GEMINI_API_KEY` to a key from [Google AI Studio](https://aistudio.google.com/apikey).
3. Adjust `CORS_ORIGINS` if the UI runs on a different host or port.

OCR endpoints raise a clear error if `GEMINI_API_KEY` is missing. Inventory and search do not require Gemini.

## Secret hygiene

- Never commit `.env` or paste API keys into source files.
- If a key was ever committed to git history, **revoke and rotate it** in Google AI Studio immediately, then put only the new key in `.env`.
- Prefer environment variables or a secret manager in any shared or hosted deployment.

## CORS notes

- Prefer explicit origins (for example `http://localhost:8501`).
- `CORS_ORIGINS=*` disables credentialed CORS (browsers disallow `*` with credentials). Use a wildcard only for quick local experiments.
