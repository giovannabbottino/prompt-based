# Prompt-based Knowledge Graph API

Flask API that extracts knowledge graphs from text using Ollama and prompts, without external Wikidata queries. The model returns `{"rdf": "...Turtle..."}`. The service validates the JSON and RDF before logging each attempt and returning the Turtle string.

## Run

Requires Python 3.12 and Ollama.

```bash
python -m pip install -e ".[dev]"
cp .env.example .env
ollama pull llama3.1:8b
python -m prompt_based
```

Edit `.env` to configure the model, prompts, logs, and generation options. The application loads it automatically. If `.env` already exists, edit it instead of copying over it. See [setup instructions](docs/how-to-run.md) for virtual environment activation.

## Use

```bash
curl -X POST http://127.0.0.1:5000/analyze \
  -H "Content-Type: application/json" \
  -d '{"text":"Alice knows Bob."}'
```

`GET /health` checks Ollama and the configured model. See the [API contract](docs/analyze.md).
