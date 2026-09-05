import csv
from pathlib import Path

from prompt_based.domain.rdf_validation import rdf_validation_result
from prompt_based.infrastructure.ollama_client import (
    OllamaClient,
    OllamaClientConfig,
    OllamaOptions,
)


def test_strict_validation_rejects_predicate_after_comma() -> None:
    invalid_rdf = """\
@prefix kg: <https://example.org/kg/> .
kg:java kg:is kg:language,
  kg:allows kg:portable_code .
"""

    valid, note = rdf_validation_result(invalid_rdf)

    assert valid is False
    assert "Bad syntax" in note


def test_strict_validation_accepts_objects_then_new_predicate() -> None:
    valid_rdf = """\
@prefix kg: <https://example.org/kg/> .
kg:java kg:is kg:language, kg:object_oriented_language ;
  kg:allows kg:portable_code .
"""

    valid, note = rdf_validation_result(valid_rdf)

    assert valid is True
    assert note == ""


def test_strict_validation_extracts_fenced_turtle() -> None:
    response = """\
```turtle
@prefix kg: <https://example.org/kg/> .
kg:java kg:is kg:language .
```
"""

    valid, note = rdf_validation_result(response)

    assert valid is True
    assert note == ""


def test_csv_records_strict_parser_failure(tmp_path: Path) -> None:
    csv_path = tmp_path / "ollama.csv"
    client = OllamaClient(
        OllamaClientConfig(
            url="http://ollama:11434",
            model="llama3.1:8b",
            csv_path=csv_path,
            options=OllamaOptions(),
            timeout_seconds=30,
        )
    )
    invalid_rdf = """\
@prefix kg: <https://example.org/kg/> .
kg:java kg:is kg:language,
  kg:allows kg:portable_code .
"""

    client._log_to_csv(
        {"response": invalid_rdf},
        prompt_name="prompts/few-shot.txt",
        input_text="Java input",
    )

    with csv_path.open(encoding="utf-8", newline="") as csv_file:
        row = next(csv.DictReader(csv_file))
    assert row["rdf_valid"] == "False"
    assert "Bad syntax" in row["rdf_note"]
