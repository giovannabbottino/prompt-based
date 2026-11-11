# Run guide

[README](../README.md) · [API](analyze.md) · [Testing](how-to-test.md)

## Requirements

Use Python 3.12. A running Ollama instance with the configured model. Run all commands from `prompt-based/` in the combined workspace, or the repository root if this project is checked out separately.

## Install

PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

Bash (Linux/macOS):

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

## Configure and start

Copy [.env.example](../.env.example) only if `.env` does not exist:

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

Bash equivalent: `test -f .env || cp .env.example .env`.

Edit the model, endpoints, limits, and log paths in `.env`. The application loads this file automatically. Keep Ollama running (start `ollama serve` in a separate terminal if necessary), then run:

```powershell
ollama pull llama3.1:8b
python -m prompt_based
```

If you change the model in `.env`, pull that model instead. The default address is `http://127.0.0.1:5000`.

## Verify

From another terminal:

```powershell
Invoke-RestMethod http://127.0.0.1:5000/health
```

Bash equivalent: `curl http://127.0.0.1:5000/health`. Once healthy, send the [README request](../README.md#usage). See the [API](analyze.md) for error codes.

## Pipeline settings

No Wikidata endpoint is required. Configure the system and example templates with `DEFAULT_SYSTEM_PROMPT_NAME` and `DEFAULT_PROMPT_NAME`.

`OLLAMA_TIMEOUT_SECONDS` defaults to 300 seconds per call. `max_rdf_attempts` is clamped to 1–3.

## Logs and troubleshooting

Runtime log directories are created automatically. Inspect `logs/analyze_log.jsonl` for request events and `logs/ollama_responses.jsonl` for model responses.

- For HTTP 503, inspect the health response and check the configured dependencies.
- For timeouts, check the service endpoints and adjust the relevant timeout in `.env`.
- For invalid or truncated RDF, inspect the validation error and generation token limit.
- After changing dependencies, reinstall with `python -m pip install -e ".[dev]"`.
