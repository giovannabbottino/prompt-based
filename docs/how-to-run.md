# How to run

## Environment variables

The application loads `.env` when running locally and also accepts regular environment variables. Docker Compose sets the production-like defaults for this service.

- `DEFAULT_PROMPT_NAME=prompts/few-shot.txt`
- `DEFAULT_SYSTEM_PROMPT_NAME=system/knowledge_graph.txt`
- `OLLAMA_API_URL=http://localhost:11434`
- `OLLAMA_MODEL=llama3:8b`
- `OLLAMA_CSV_PATH=data/ollama_responses.csv`
- `OLLAMA_TIMEOUT_SECONDS=180`
- Generation options, all optional and ignored when blank: `OLLAMA_SEED`, `OLLAMA_TEMPERATURE`, `OLLAMA_TOP_K`, `OLLAMA_TOP_P`, `OLLAMA_MIN_P`, `OLLAMA_STOP`, `OLLAMA_NUM_CTX`, `OLLAMA_NUM_PREDICT`.

## Requirements

- Python >=3.10
- Ollama with the configured model installed

## Run with Docker Compose

From the repository root:

```powershell
docker compose up --build -d prompt-based
```

On first run, pull the configured model into the Ollama container:

```powershell
docker exec -it kg-ollama ollama pull llama3:8b
```

Check the service:

```powershell
Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:5000/health"
```

Analyze text:

```powershell
$body = @{
  text = "Mango is a tropical fruit."
} | ConvertTo-Json

Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:5000/analyze" `
  -ContentType "application/json" `
  -Body $body
```

Generated Ollama responses are logged to `prompt-based/data/ollama_responses.csv` because Docker Compose mounts `./prompt-based/data` to `/app/data`.

## Run locally

Run commands from `prompt-based/`.

### 1. Install Python dependencies

Linux / macOS:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

### 2. Install and configure Ollama

Windows/Mac: download from [https://ollama.ai](https://ollama.ai).

Download the model:

```bash
ollama pull llama3:8b
```

Start Ollama if it is not already running:

```bash
ollama serve
```

### 3. Configure local defaults

Create a local `.env` file when you want to override defaults:

```text
DEFAULT_PROMPT_NAME=prompts/few-shot.txt
DEFAULT_SYSTEM_PROMPT_NAME=system/knowledge_graph.txt
OLLAMA_API_URL=http://localhost:11434
OLLAMA_MODEL=llama3:8b
OLLAMA_CSV_PATH=data/ollama_responses.csv
OLLAMA_TIMEOUT_SECONDS=180
OLLAMA_NUM_PREDICT=768
```

### 4. Run the API

```bash
python -m kg_construction.app
```

The service listens on `http://127.0.0.1:5000`.

## Troubleshooting

- `missing_model` in `/health`: run `ollama pull llama3:8b`.
- `Failed to generate response from model`: check that Ollama is running and `OLLAMA_API_URL` points to it.
- `RDF parsing failed`: the model did not return valid Turtle after the configured attempts. Try a smaller input, a stricter prompt, or a higher `OLLAMA_NUM_PREDICT`.
