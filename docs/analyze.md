# API

[README](../README.md) · [Run guide](how-to-run.md) · [Prompts](prompt.md)

## GET /health

Returns `200` when Ollama and the configured model are available; otherwise `503`. The body includes `status` and `ollama` with availability details.

## POST /analyze

### Request

Accepts a JSON object. Only `text` is required.

```json
{"text": "Alice knows Bob."}
```

| Field | Description |
| --- | --- |
| `text` | Non-empty source text. Outer whitespace is trimmed. |
| `prompt_name` | Optional template path under `prompt/`; defaults to the setting in `.env`. |
| `system_prompt_name` | Optional system prompt path under `prompt/`; defaults to the setting in `.env`. |
| `max_rdf_attempts` | Optional integer, clamped to 1-3; defaults to 3. |
| `idempotence_key` | Optional log correlation key; generated when omitted. Does not deduplicate requests. |

### Processing and response

Success (`200`):

```json
{
  "text": "Alice knows Bob.",
  "rdf": "@prefix kg: <https://example.org/wikidata-description/> .\nkg:alice kg:knows kg:bob ."
}
```

The service validates the [model response](prompt.md), records the result in JSONL, and returns the extracted Turtle. Invalid output is retried with feedback using the same model.

### Status codes

| Status | Cause |
| --- | --- |
| `200` | Analysis completed. |
| `400` | Invalid request fields or prompt path. |
| `404` | Prompt file not found. |
| `422` | Invalid model output after all attempts; includes `attempts` and `details`. |
| `502` | Ollama request failed or model unavailable. |
| `504` | Ollama request timed out. |

Errors include an `error` message.

## Configuration and logs

Configure the model and log paths in `.env`; see [.env.example](../.env.example).
