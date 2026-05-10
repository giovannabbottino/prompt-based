from pathlib import Path

import pytest

from src.application.services import KnowledgeGraphService
from src.domain.models import AnalyzeRequest
from src.infrastructure.prompt_repository import PromptRepository


class DummyPromptRepo(PromptRepository):
    def __init__(self, prompt_text: str):
        super().__init__(prompt_dir=Path("unused"))
        self.prompt_text = prompt_text

    def load_prompt(self, prompt_name: str) -> str:  # type: ignore[override]
        return self.prompt_text


def test_analyze_builds_payload():
    repo = DummyPromptRepo(prompt_text="Example Prompt")
    service = KnowledgeGraphService(repo, default_prompt="example.txt", default_system_prompt="system.txt")
    request = AnalyzeRequest(text="Hello world", prompt_name="example.txt", system_prompt_name="system.txt")

    response = service.analyze(request)

    assert response.prompt_name == "example.txt"
    assert response.prompt == "Example Prompt"
    assert response.input_text == "Hello world"
    assert "User: Hello world" in response.message_for_model
    assert response.message_for_model.startswith("Example Prompt")


def test_analyze_replaces_placeholder():
    repo = DummyPromptRepo(prompt_text="Prompt with ${USER_TEXT} inside")
    service = KnowledgeGraphService(repo, default_prompt="example.txt", default_system_prompt="system.txt")
    request = AnalyzeRequest(text="Hello", prompt_name="example.txt", system_prompt_name="system.txt")

    response = service.analyze(request)

    assert response.message_for_model == "Prompt with Hello inside"


def test_analyze_replaces_legacy_text_placeholder():
    repo = DummyPromptRepo(prompt_text="Prompt with ${Text_TEXT} inside")
    service = KnowledgeGraphService(repo, default_prompt="example.txt", default_system_prompt="system.txt")
    request = AnalyzeRequest(text="Hello", prompt_name="example.txt", system_prompt_name="system.txt")

    response = service.analyze(request)

    assert response.message_for_model == "Prompt with Hello inside"


def test_analyze_retries_until_rdf_is_valid():
    class StubOllamaClient:
        def __init__(self):
            self.responses = ["not rdf", "<http://example.org/s> <http://example.org/p> <http://example.org/o> ."]
            self.prompts = []

        def generate(self, system_prompt: str, prompt: str, prompt_name: str | None = None, input_text: str | None = None):
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
    request = AnalyzeRequest(text="Hello", prompt_name="example.txt", system_prompt_name="system.txt", max_rdf_attempts=3)

    response = service.analyze(request)

    assert response.generation["response"] == "<http://example.org/s> <http://example.org/p> <http://example.org/o> ."
    assert response.generation["rdf_validation_attempts"] == 2
    assert len(ollama.prompts) == 2
    assert "previous answer was not valid Turtle RDF" in ollama.prompts[1]


def test_analyze_repairs_doubled_literal_quotes():
    class StubOllamaClient:
        def generate(self, system_prompt: str, prompt: str, prompt_name: str | None = None, input_text: str | None = None):
            return {
                "response": (
                    "@prefix ex: <http://example.org/kg/> .\n"
                    "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n\n"
                    'ex:coqa rdfs:label ""CoQA"" .'
                )
            }

    service = KnowledgeGraphService(
        DummyPromptRepo(prompt_text="Prompt with ${USER_TEXT} inside"),
        default_prompt="example.txt",
        default_system_prompt="system.txt",
        ollama_client=StubOllamaClient(),
    )

    response = service.analyze(AnalyzeRequest(text="Hello", prompt_name="example.txt", system_prompt_name="system.txt"))

    assert '""CoQA""' not in response.generation["response"]
    assert '"CoQA"' in response.generation["response"]


def test_analyze_drops_incomplete_last_statement():
    class StubOllamaClient:
        def generate(self, system_prompt: str, prompt: str, prompt_name: str | None = None, input_text: str | None = None):
            return {
                "response": (
                    "@prefix ex: <http://example.org/kg/> .\n"
                    "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n\n"
                    'ex:valid rdfs:label "Valid" .\n\n'
                    'ex:cut rdfs:label "Cut'
                )
            }

    service = KnowledgeGraphService(
        DummyPromptRepo(prompt_text="Prompt with ${USER_TEXT} inside"),
        default_prompt="example.txt",
        default_system_prompt="system.txt",
        ollama_client=StubOllamaClient(),
    )

    response = service.analyze(AnalyzeRequest(text="Hello", prompt_name="example.txt", system_prompt_name="system.txt"))

    assert 'ex:valid rdfs:label "Valid" .' in response.generation["response"]
    assert "ex:cut" not in response.generation["response"]
    assert response.generation["rdf_repair_method"] in {
        "keep_through_last_complete_statement",
        "drop_incomplete_last_block",
    }
