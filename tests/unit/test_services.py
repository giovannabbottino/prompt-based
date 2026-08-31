import json
from pathlib import Path

import pytest

from prompt_based.application.services import KnowledgeGraphService, RDFValidationError
from prompt_based.domain.models import AnalyzeRequest
from prompt_based.infrastructure.prompt_repository import PromptRepository
from prompt_based.infrastructure.request_logger import RequestLogger


class DummyPromptRepo(PromptRepository):
    def __init__(self, prompt_text: str):
        super().__init__(prompt_dir=Path("unused"))
        self.prompt_text = prompt_text

    def load_prompt(self, prompt_name: str) -> str:
        return self.prompt_text


def test_analyze_logs_request_lifecycle_with_idempotence_key(tmp_path):
    class StubOllamaClient:
        def generate(
            self,
            system_prompt: str,
            prompt: str,
            prompt_name: str | None = None,
            input_text: str | None = None,
        ):
            return {
                "response": (
                    "<http://example.org/s> <http://example.org/p> "
                    "<http://example.org/o> ."
                )
            }

    log_path = tmp_path / "analyze.jsonl"
    service = KnowledgeGraphService(
        DummyPromptRepo(prompt_text="Build RDF for ${USER_TEXT}"),
        default_prompt="example.txt",
        default_system_prompt="system.txt",
        ollama_client=StubOllamaClient(),
        request_logger=RequestLogger(log_path),
    )

    service.analyze(AnalyzeRequest(text="Hello", idempotence_key="request-123"))

    entries = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    assert {entry["idempotence_key"] for entry in entries} == {"request-123"}
    assert [entry["event"] for entry in entries] == [
        "analyze_started",
        "llm_rdf_request",
        "llm_rdf_response",
        "rdf_validated",
        "analyze_completed",
    ]


def test_analyze_builds_payload():
    repo = DummyPromptRepo(prompt_text="Example Prompt")
    service = KnowledgeGraphService(
        repo, default_prompt="example.txt", default_system_prompt="system.txt"
    )
    request = AnalyzeRequest(
        text="Hello world", prompt_name="example.txt", system_prompt_name="system.txt"
    )

    response = service.analyze(request)

    assert response.prompt_name == "example.txt"
    assert response.prompt == "Example Prompt"
    assert response.input_text == "Hello world"
    assert "User: Hello world" in response.message_for_model
    assert response.message_for_model.startswith("Example Prompt")


def test_analyze_replaces_placeholder():
    repo = DummyPromptRepo(prompt_text="Prompt with ${USER_TEXT} inside")
    service = KnowledgeGraphService(
        repo, default_prompt="example.txt", default_system_prompt="system.txt"
    )
    request = AnalyzeRequest(
        text="Hello", prompt_name="example.txt", system_prompt_name="system.txt"
    )

    response = service.analyze(request)

    assert response.message_for_model == "Prompt with Hello inside"


def test_analyze_replaces_legacy_text_placeholder():
    repo = DummyPromptRepo(prompt_text="Prompt with ${Text_TEXT} inside")
    service = KnowledgeGraphService(
        repo, default_prompt="example.txt", default_system_prompt="system.txt"
    )
    request = AnalyzeRequest(
        text="Hello", prompt_name="example.txt", system_prompt_name="system.txt"
    )

    response = service.analyze(request)

    assert response.message_for_model == "Prompt with Hello inside"


def test_analyze_retries_until_rdf_is_valid():
    class StubOllamaClient:
        def __init__(self):
            self.responses = [
                "not rdf",
                "<http://example.org/s> <http://example.org/p> <http://example.org/o> .",
            ]
            self.prompts = []

        def generate(
            self,
            system_prompt: str,
            prompt: str,
            prompt_name: str | None = None,
            input_text: str | None = None,
        ):
            self.prompts.append(prompt)
            return {"response": self.responses.pop(0)}

    repo = DummyPromptRepo(prompt_text="Prompt with ${USER_TEXT} inside")
    ollama = StubOllamaClient()
    service = KnowledgeGraphService(
        repo,
        default_prompt="example.txt",
        default_system_prompt="system.txt",
        ollama_client=ollama,
    )
    request = AnalyzeRequest(
        text="Hello", prompt_name="example.txt", system_prompt_name="system.txt", max_rdf_attempts=3
    )

    response = service.analyze(request)

    generation = response.generation
    assert generation is not None
    assert (
        generation["response"]
        == "<http://example.org/s> <http://example.org/p> <http://example.org/o> ."
    )
    assert generation["rdf_validation_attempts"] == 2
    assert len(ollama.prompts) == 2
    assert "previous answer was not valid Turtle RDF" in ollama.prompts[1]
    assert "Previous invalid RDF:\nnot rdf" in ollama.prompts[1]
    assert "every statement conforms to the standard RDF/Turtle grammar" in ollama.prompts[1]
    assert "correct the entire RDF document" in ollama.prompts[1]


def test_analyze_retries_when_rdf_has_only_prefixes():
    class StubOllamaClient:
        def __init__(self):
            self.responses = [
                "@prefix kg: <https://example.org/wikidata-description/> .",
                "@prefix kg: <https://example.org/wikidata-description/> .\n"
                "kg:mango kg:is kg:fruit .",
            ]
            self.prompts = []

        def generate(self, system_prompt, prompt, prompt_name=None, input_text=None):
            self.prompts.append(prompt)
            return {"response": self.responses.pop(0)}

    service = KnowledgeGraphService(
        DummyPromptRepo(prompt_text="Prompt with ${USER_TEXT} inside"),
        default_prompt="example.txt",
        default_system_prompt="system.txt",
        ollama_client=StubOllamaClient(),
    )

    response = service.analyze(
        AnalyzeRequest(
            text="Mango is a fruit.",
            prompt_name="example.txt",
            system_prompt_name="system.txt",
            max_rdf_attempts=3,
        )
    )

    generation = response.generation
    assert generation is not None
    assert generation["rdf_validation_attempts"] == 2
    assert "kg:mango kg:is kg:fruit" in generation["response"]


@pytest.mark.parametrize(
    "invalid_rdf",
    [
        (
            "@prefix ex: <http://example.org/kg/> .\n"
            "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n\n"
            'ex:coqa rdfs:label ""CoQA"" ;\n'
            "    ex:related ex:dataset ."
        ),
        (
            "@prefix ex: <http://example.org/kg/> .\n"
            "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n\n"
            'ex:valid rdfs:label "Valid" ;\n'
            "    ex:related ex:dataset .\n\n"
            'ex:cut rdfs:label "Cut'
        ),
        (
            "@prefix kg: <https://example.org/wikidata-description/> .\n"
            'kg:mustang kg:production_year "1964"^^xsd:gYear .'
        ),
        (
            "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n"
            "@prefix wd: <http://www.wikidata.org/entity/> .\n"
            "@prefix kg: <https://example.org/wikidata-description/> .\n"
            'wd:Q? rdfs:label "calendar date"@en ; kg:is kg:date .\n'
            "."
        ),
        (
            "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n"
            "@prefix kg: <https://example.org/wikidata-description/> .\n"
            'kg:bank rdfs:label "Bank"@en ;\n'
            "  kg:is kg:financial_institution ;\n"
            "  kg:accepts_deposits ;\n"
            "  kg:makes_loans ."
        ),
    ],
)
def test_analyze_rejects_invalid_rdf_without_local_repair(invalid_rdf):
    class StubOllamaClient:
        def generate(
            self,
            system_prompt: str,
            prompt: str,
            prompt_name: str | None = None,
            input_text: str | None = None,
        ):
            return {"response": invalid_rdf}

    service = KnowledgeGraphService(
        DummyPromptRepo(prompt_text="Prompt with ${USER_TEXT} inside"),
        default_prompt="example.txt",
        default_system_prompt="system.txt",
        ollama_client=StubOllamaClient(),
    )

    with pytest.raises(RDFValidationError):
        service.analyze(
            AnalyzeRequest(
                text="Hello",
                prompt_name="example.txt",
                system_prompt_name="system.txt",
                max_rdf_attempts=1,
            )
        )


def test_analyze_retries_instead_of_dropping_complete_invalid_blocks():
    class StubOllamaClient:
        def __init__(self):
            self.responses = [
                (
                    "@prefix kg: <https://example.org/kg/> .\n"
                    "kg:first kg:is kg:valid .\n\n"
                    "kg:second kg:on kg:date extra ."
                ),
                (
                    "@prefix kg: <https://example.org/kg/> .\n"
                    "kg:first kg:is kg:valid .\n"
                    "kg:second kg:on kg:date ."
                ),
            ]

        def generate(self, system_prompt, prompt, prompt_name=None, input_text=None):
            return {"response": self.responses.pop(0)}

    service = KnowledgeGraphService(
        DummyPromptRepo(prompt_text="Prompt with ${USER_TEXT} inside"),
        default_prompt="example.txt",
        default_system_prompt="system.txt",
        ollama_client=StubOllamaClient(),
    )

    response = service.analyze(AnalyzeRequest(text="Two senses.", max_rdf_attempts=2))

    generation = response.generation
    assert generation is not None
    assert "kg:second" in generation["response"]
    assert generation["rdf_validation_attempts"] == 2
