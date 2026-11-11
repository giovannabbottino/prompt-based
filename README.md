# Prompt-based Knowledge Graph API

Flask API that builds RDF/Turtle knowledge graphs from text using Ollama and few-shot prompts, without external Wikidata queries.

## Requirements

- Python 3.12 (the supported runtime).
- A running Ollama instance with the configured model.

## Quick start

Run from this project directory (`prompt-based/` when using the combined workspace):

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
ollama pull llama3.1:8b
python -m prompt_based
```

Keep Ollama running. Edit `.env` using [.env.example](.env.example); the application loads it automatically. If you select another model, pull that model instead. See the [run guide](docs/how-to-run.md) for Bash instructions and troubleshooting.

## Usage

The default API address is `http://127.0.0.1:5000`. From another terminal:

```powershell
Invoke-RestMethod http://127.0.0.1:5000/health
$body = @{ text = "Mango is a tropical fruit." } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:5000/analyze -ContentType application/json -Body $body
```

The model generates RDF directly from the system prompt, examples, and input text. Invalid output is retried with validation feedback. The model returns `{"rdf":"<Turtle>"}`; the service validates it and allows up to three RDF attempts. See the [API contract](docs/analyze.md) for request fields, response fields, and errors.

## Configuration and logs

[.env.example](.env.example) lists the available settings. Defaults include `llama3.1:8b`, seed 42, temperature 0, and a 2048-token generation limit. Events and model responses are logged to `logs/analyze_log.jsonl` and `logs/ollama_responses.jsonl`.

## Quality checks

With the virtual environment active:

```powershell
python -m ruff format --check .
python -m ruff check .
python -m pyright
python -m pytest
```

Tests use doubles for external services. CI runs the same checks on Python 3.12 for pushes, pull requests, and manual runs.

## Project structure

- [src/prompt_based/](src/prompt_based/): application, domain, infrastructure, and HTTP controllers.
- [prompt/](prompt/): system instructions and task templates.
- [tests/](tests/): automated checks.
- [docs/](docs/): operational and API documentation.

## Documentation

[Run guide](docs/how-to-run.md) · [API](docs/analyze.md) · [Prompts](docs/prompt.md) · [Testing](docs/how-to-test.md)
