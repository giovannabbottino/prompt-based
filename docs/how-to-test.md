# How to test

Tests are organized by scope:
- `tests/unit/` for service behavior, prompt substitution, RDF validation, retries, and repair logic.
- `tests/integration/` for request flows through the Flask app factory with mocked Ollama calls and temporary prompt files.

## Run all tests

Run commands from `prompt-based/`.

```bash
python -m pip install -r requirements-dev.txt
python -m pytest
```

## Run a specific scope

```bash
python -m pytest tests/unit
python -m pytest tests/integration
```

## Useful focused runs

```bash
python -m pytest tests/unit/test_services.py
python -m pytest tests/integration/test_app_requests.py
```

## Notes

- The project uses the standard `src` package layout and is installed in editable mode by
  `requirements-dev.txt`.
- Pytest writes temporary files under `.pytest-runtime` through the configured `--basetemp`.
- Integration tests mock external generation calls; Ollama does not need to be running for the test suite.
