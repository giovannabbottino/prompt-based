# Tests and quality checks

Run from `prompt-based/` with the virtual environment active:

```bash
python -m pip install -e ".[dev]"
python -m ruff format --check .
python -m ruff check .
python -m pyright
python -m pytest
```

Tests cover prompts, validation, retries, JSONL logging, and API requests. Ollama calls are mocked; the model does not need to be running. To run one scope, use `python -m pytest tests/unit` or `python -m pytest tests/integration`.
