# Run locally

Requires Python 3.12 and a running Ollama instance. Run these commands from `prompt-based/`.

## Install

```bash
python -m venv .venv
```

Activate with `.venv\Scripts\Activate.ps1` in PowerShell or `source .venv/bin/activate` on Linux/macOS. Then install dependencies:

```bash
python -m pip install -e ".[dev]"
```

## Configure and start

Copy [.env.example](../.env.example) to `.env` (`cp .env.example .env`; PowerShell also accepts `Copy-Item .env.example .env`). Edit the values in `.env`; existing settings can be kept. The application loads this file automatically.

```bash
ollama pull llama3.1:8b
python -m prompt_based
```

If you change the model in `.env`, pull that model instead. The API runs at `http://127.0.0.1:5000`. Check `/health` before sending an [analysis request](analyze.md).

If Ollama is stopped, run `ollama serve`. If generation fails, inspect the response's `details` and the JSONL logs. For truncated output, increase the generation limit in `.env`.
