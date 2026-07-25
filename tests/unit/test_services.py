from pathlib import Path

from kg_construction.application.services import KnowledgeGraphService
from kg_construction.domain.models import AnalyzeRequest
from kg_construction.infrastructure.prompt_repository import PromptRepository


class DummyPromptRepo(PromptRepository):
    def __init__(self, prompt_text: str):
        super().__init__(prompt_dir=Path("unused"))
        self.prompt_text = prompt_text

    def load_prompt(self, prompt_name: str) -> str:
        return self.prompt_text


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

    assert response.generation["rdf_validation_attempts"] == 2
    assert "kg:mango kg:is kg:fruit" in response.generation["response"]


def test_analyze_repairs_doubled_literal_quotes():
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
                    "@prefix ex: <http://example.org/kg/> .\n"
                    "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n\n"
                    'ex:coqa rdfs:label ""CoQA"" ;\n'
                    "    ex:related ex:dataset ."
                )
            }

    service = KnowledgeGraphService(
        DummyPromptRepo(prompt_text="Prompt with ${USER_TEXT} inside"),
        default_prompt="example.txt",
        default_system_prompt="system.txt",
        ollama_client=StubOllamaClient(),
    )

    response = service.analyze(
        AnalyzeRequest(text="Hello", prompt_name="example.txt", system_prompt_name="system.txt")
    )

    generation = response.generation
    assert generation is not None
    assert '""CoQA""' not in generation["response"]
    assert '"CoQA"' in generation["response"]


def test_analyze_drops_incomplete_last_statement():
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
                    "@prefix ex: <http://example.org/kg/> .\n"
                    "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n\n"
                    'ex:valid rdfs:label "Valid" ;\n'
                    "    ex:related ex:dataset .\n\n"
                    'ex:cut rdfs:label "Cut'
                )
            }

    service = KnowledgeGraphService(
        DummyPromptRepo(prompt_text="Prompt with ${USER_TEXT} inside"),
        default_prompt="example.txt",
        default_system_prompt="system.txt",
        ollama_client=StubOllamaClient(),
    )

    response = service.analyze(
        AnalyzeRequest(text="Hello", prompt_name="example.txt", system_prompt_name="system.txt")
    )

    generation = response.generation
    assert generation is not None
    assert 'ex:valid rdfs:label "Valid"' in generation["response"]
    assert "ex:cut" not in generation["response"]
    assert generation["rdf_repair_method"] in {
        "keep_through_last_complete_statement",
        "drop_incomplete_last_block",
    }


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

    assert "kg:second" in response.generation["response"]
    assert response.generation["rdf_validation_attempts"] == 2

def test_analyze_adds_missing_xsd_prefix_without_retry():
    class StubOllamaClient:
        def generate(self, system_prompt, prompt, prompt_name=None, input_text=None):
            return {
                "response": (
                    "@prefix kg: <https://example.org/wikidata-description/> .\n"
                    'kg:mustang kg:production_year "1964"^^xsd:gYear .'
                )
            }

    service = KnowledgeGraphService(
        DummyPromptRepo(prompt_text="Prompt with ${USER_TEXT} inside"),
        default_prompt="example.txt",
        default_system_prompt="system.txt",
        ollama_client=StubOllamaClient(),
    )

    response = service.analyze(AnalyzeRequest(text="Mustang", max_rdf_attempts=1))

    assert "@prefix xsd:" in response.generation["response"]
    assert response.generation["rdf_repair_method"] == "normalize_common_turtle_errors"


def test_analyze_replaces_invalid_wikidata_placeholder_and_stray_dot():
    class StubOllamaClient:
        def generate(self, system_prompt, prompt, prompt_name=None, input_text=None):
            return {
                "response": (
                    "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n"
                    "@prefix wd: <http://www.wikidata.org/entity/> .\n"
                    "@prefix kg: <https://example.org/wikidata-description/> .\n"
                    'wd:Q? rdfs:label "calendar date"@en ; kg:is kg:date .\n'
                    "."
                )
            }

    service = KnowledgeGraphService(
        DummyPromptRepo(prompt_text="Prompt with ${USER_TEXT} inside"),
        default_prompt="example.txt",
        default_system_prompt="system.txt",
        ollama_client=StubOllamaClient(),
    )

    response = service.analyze(AnalyzeRequest(text="Date", max_rdf_attempts=1))

    assert "wd:Q?" not in response.generation["response"]
    assert "kg:calendar_date" in response.generation["response"]
    assert response.generation["rdf_repair_method"] == "normalize_common_turtle_errors"


def test_analyze_salvages_valid_clauses_from_invalid_subject_block():
    class StubOllamaClient:
        def generate(self, system_prompt, prompt, prompt_name=None, input_text=None):
            return {
                "response": (
                    "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n"
                    "@prefix kg: <https://example.org/wikidata-description/> .\n"
                    'kg:bank rdfs:label "Bank"@en ;\n'
                    "  kg:is kg:financial_institution ;\n"
                    "  kg:accepts_deposits ;\n"
                    "  kg:makes_loans ."
                )
            }

    service = KnowledgeGraphService(
        DummyPromptRepo(prompt_text="Prompt with ${USER_TEXT} inside"),
        default_prompt="example.txt",
        default_system_prompt="system.txt",
        ollama_client=StubOllamaClient(),
    )

    response = service.analyze(AnalyzeRequest(text="Bank", max_rdf_attempts=1))

    rdf = response.generation["response"]
    assert "financial_institution" in rdf
    assert "accepts_deposits" not in rdf
    assert "makes_loans" not in rdf
    assert response.generation["rdf_repair_method"] == "salvage_parseable_statements"

