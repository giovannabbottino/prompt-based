# Tests and quality checks

[README](../README.md) · [Run guide](how-to-run.md)

## Setup

Use Python 3.12 and activate the project virtual environment as described in the [run guide](how-to-run.md). Run from this project directory:

```powershell
python -m pip install -e ".[dev]"
```

## Automated checks

Run the same checks as CI, in this order:

```powershell
python -m ruff format --check .
python -m ruff check .
python -m pyright
python -m pytest
```

These commands also work in Bash. Formatting and lint checks do not modify files. To apply formatting intentionally, run `python -m ruff format .`.

## Test coverage

Unit and integration tests cover prompts, structured RDF validation, retries, clients, JSONL logging, and HTTP endpoints. External calls are replaced with test doubles; Ollama and Wikidata are not required.

Run only unit tests with `python -m pytest tests/unit`. Run only integration tests with `python -m pytest tests/integration`; these also use test doubles.

## Live verification

Start the dependencies and API following the [run guide](how-to-run.md). Check `GET /health`, then send the [README example](../README.md#usage). Inspect the RDF and JSONL logs. Live checks depend on model behavior and network availability and are not part of CI.
