
# Analyze

## `GET /health`

Checks the API and the configured Ollama model.

Example response when the model is available:

```json
{
  "status": "ok",
  "ollama": {
    "status": "ok",
    "model": "llama3:8b"
  }
}
```

If Ollama is reachable but the configured model is missing, `ollama.status` is `missing_model` and the response includes the pull command.

## `POST /analyze`

Builds a prompt from the input text, calls Ollama, validates the generated Turtle RDF, logs the generation metadata to CSV, and returns the validated RDF.

### Request body

```json
{
  "text": "Alice knows Bob.",
  "prompt_name": "prompts/few-shot.txt",
  "system_prompt_name": "system/knowledge_graph.txt",
  "max_rdf_attempts": 3
}
```

Fields:

| Field | Required | Description |
|-------|----------|-------------|
| `text` | Yes | Source text to convert into a knowledge graph. |
| `prompt_name` | No | Prompt template path under `prompt/`. Defaults to `DEFAULT_PROMPT_NAME`. |
| `system_prompt_name` | No | System prompt path under `prompt/`. Defaults to `DEFAULT_SYSTEM_PROMPT_NAME`. |
| `max_rdf_attempts` | No | Number of RDF generation/repair attempts. Values are clamped between 1 and 3. Default: `3`. |

Prompt paths are resolved under the local `prompt/` directory. Path traversal outside that directory is rejected.

### Prompt construction

The service loads both prompt files and then:

- replaces `${USER_TEXT}` or `${Text_TEXT}` with `text`, when either placeholder is present;
- otherwise appends the input as:

```text
User: <text>
Assistant:
```

### RDF validation and repair

The model response is normalized before validation:

- markdown fences are removed;
- leading non-RDF prose is discarded when a Turtle marker is found;
- common quote issues are repaired;
- incomplete trailing blocks can be removed when a complete RDF statement exists.

The final candidate is parsed with `rdflib.Graph.parse(..., format="turtle")`. If parsing fails and attempts remain, the service asks the model to return corrected Turtle only.

### Example request

```bash
curl -X POST http://127.0.0.1:5000/analyze \
  -H "Content-Type: application/json" \
  -d '{"text":"Alice knows Bob."}'
```

PowerShell:

```powershell
$body = @{
  text = "Alice knows Bob."
} | ConvertTo-Json

Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:5000/analyze" `
  -ContentType "application/json" `
  -Body $body
```

### Success response

```json
{
  "text": "Alice knows Bob.",
  "rdf": "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n@prefix wd: <http://www.wikidata.org/entity/> .\n@prefix kg: <https://example.org/wikidata-description/> .\n\nkg:alice a kg:Person ;\n  rdfs:label \"Alice\"@en ;\n  kg:knows kg:bob .\n\nkg:bob a kg:Person ;\n  rdfs:label \"Bob\"@en ."
}
```

### Error responses

| Status | Cause | Response shape |
|--------|-------|----------------|
| `400` | Missing `text` or invalid prompt path | `{ "error": "..." }` |
| `404` | Prompt file not found | `{ "error": "..." }` |
| `502` | Ollama request failed or model is unavailable | `{ "error": "...", "details": "..." }` |
| `508` | RDF could not be parsed after all attempts | `{ "error": "rdf parse errror", "attempts": 3, "details": "..." }` |
