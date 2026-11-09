import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from prompt_based.application.services import KnowledgeGraphService, RDFValidationError
from prompt_based.domain.models import AnalyzeRequest
from prompt_based.infrastructure.prompt_repository import PromptRepository
from prompt_based.infrastructure.request_logger import RequestLogger

VALID_RDF = "@prefix kg: <https://example.org/wikidata-description/> .\nkg:alice kg:knows kg:bob ."


VALID_RESPONSE = json.dumps({"rdf": VALID_RDF})


class DummyPromptRepo(PromptRepository):
    def __init__(self, prompt_text: str):
        super().__init__(prompt_dir=Path("unused"))
        self.prompt_text = prompt_text

    def load_prompt(self, prompt_name: str) -> str:
        return self.prompt_text


def make_service(client, prompt="Build RDF for ${USER_TEXT}", **kwargs):
    return KnowledgeGraphService(
        DummyPromptRepo(prompt),
        default_prompt="example.txt",
        default_system_prompt="system.txt",
        ollama_client=client,
        **kwargs,
    )


def test_analyze_logs_request_lifecycle_with_idempotence_key(tmp_path):
    client = Mock()
    client.generate.return_value = {"response": VALID_RESPONSE}
    log_path = tmp_path / "analyze.jsonl"
    service = make_service(client, request_logger=RequestLogger(log_path))

    service.analyze(AnalyzeRequest(text="Hello", idempotence_key="request-123"))

    entries = [json.loads(line) for line in log_path.read_text().splitlines()]
    assert {entry["idempotence_key"] for entry in entries} == {"request-123"}
    assert [entry["event"] for entry in entries] == [
        "analyze_started",
        "llm_rdf_request",
        "rdf_validated",
        "analyze_completed",
    ]


@pytest.mark.parametrize(
    ("prompt", "message"),
    [
        ("Example Prompt", "Example Prompt\n\nUser: Hello\nAssistant:"),
        ("Prompt with ${USER_TEXT} inside", "Prompt with Hello inside"),
    ],
)
def test_analyze_builds_payload(prompt, message):
    client = Mock()
    client.generate.return_value = {"response": VALID_RESPONSE}
    response = make_service(client, prompt=prompt).analyze(AnalyzeRequest(text="Hello"))

    assert response.input_text == "Hello"
    client.generate.assert_called_once_with(system_prompt=prompt, prompt=message)


def test_analyze_validates_once_before_logging_each_attempt(tmp_path, monkeypatch):
    import prompt_based.application.services as services

    invalid = json.dumps({"rdf": "invalid Turtle"})
    raw_generation = {"response": VALID_RESPONSE, "model": "llama3.1:8b", "eval_count": 13}
    client = Mock()
    client.generate.side_effect = [{"response": invalid}, raw_generation]
    validate = Mock(wraps=services.validate_rdf)
    monkeypatch.setattr(services, "validate_rdf", validate)
    log_path = tmp_path / "generations.jsonl"
    logger = RequestLogger(log_path)
    write = logger.log

    def record_after_validation(**kwargs):
        attempt = kwargs["payload"]["attempt"]
        assert validate.call_count == attempt
        write(**kwargs)

    monkeypatch.setattr(logger, "log", record_after_validation)
    service = make_service(client, generation_logger=logger)
    response = service.analyze(AnalyzeRequest(text="Alice knows Bob.", idempotence_key="key"))

    entries = [json.loads(line) for line in log_path.read_text().splitlines()]
    assert len(entries) == 2
    assert {entry["idempotence_key"] for entry in entries} == {"key"}
    failed, succeeded = [entry["payload"] for entry in entries]
    assert failed["rdf_valid"] is False
    assert failed["rdf_note"]
    assert failed["rdf"] is None
    assert failed["generation"]["response"] == invalid
    assert succeeded["rdf_valid"] is True
    assert succeeded["rdf_note"] == ""
    assert succeeded["generation"] == raw_generation
    assert succeeded["rdf"] == response.generation["response"] == VALID_RDF
    assert raw_generation["response"] == VALID_RESPONSE
    assert succeeded["attempt"] == 2
    retry = client.generate.call_args_list[1].kwargs["prompt"]
    assert "Validation error:" in retry
    assert invalid in retry


@pytest.mark.parametrize(
    "invalid",
    [
        "not rdf",
        '{"triples": []}',
        '"RDF inside a JSON string"',
        f"```json\n{VALID_RESPONSE}\n```",
        json.dumps({"rdf": "invalid Turtle"}),
        json.dumps({"rdf": ""}),
        json.dumps({"rdf": VALID_RDF, "extra": True}),
        "@prefix kg: <https://example.org/kg/> .",
        '<https://example.org/alice> <http://www.w3.org/2000/01/rdf-schema#label> "Alice" .',
        "@prefix kg: <https://example.org/kg/> . kg:a kg:b ; kg:c .",
    ],
)
def test_analyze_rejects_invalid_responses_and_logs_exhausted_attempts(tmp_path, invalid):
    client = Mock()
    client.generate.return_value = {"response": invalid}
    log_path = tmp_path / "generations.jsonl"
    service = make_service(client, generation_logger=RequestLogger(log_path))

    with pytest.raises(RDFValidationError) as error:
        service.analyze(AnalyzeRequest(text="Hello", max_rdf_attempts=2))

    assert error.value.attempts == 2
    assert error.value.last_error
    assert client.generate.call_count == 2
    entries = [json.loads(line) for line in log_path.read_text().splitlines()]
    assert len(entries) == 2
    assert all(entry["payload"]["rdf_valid"] is False for entry in entries)


@pytest.mark.parametrize(("requested", "expected"), [(-1, 1), (0, 1), (1, 1), (3, 3), (8, 3)])
def test_analyze_clamps_attempts(requested, expected):
    client = Mock()
    client.generate.return_value = {"response": "invalid"}
    with pytest.raises(RDFValidationError) as error:
        make_service(client).analyze(AnalyzeRequest(text="Hello", max_rdf_attempts=requested))
    assert error.value.attempts == expected
    assert client.generate.call_count == expected


def test_analyze_succeeds_when_generation_log_cannot_be_written(tmp_path):
    client = Mock()
    client.generate.return_value = {"response": VALID_RESPONSE}
    service = make_service(client, generation_logger=RequestLogger(tmp_path))
    response = service.analyze(AnalyzeRequest(text="Alice knows Bob."))
    assert response.generation["response"] == VALID_RDF
