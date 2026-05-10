import json
from pathlib import Path

import pytest

from src.controllers.analyze_controller import create_analyze_blueprint
from src.application.services import KnowledgeGraphService
from src.infrastructure.prompt_repository import PromptRepository
from src.infrastructure.ollama_client import OllamaClientConfig, OllamaOptions


class StubPromptRepo(PromptRepository):
    def __init__(self, prompt_text: str, system_prompt_text: str | None = None):
        super().__init__(prompt_dir=Path("unused"))
        self.prompt_text = prompt_text
        self.system_prompt_text = system_prompt_text or "System prompt content"

    def load_prompt(self, prompt_name: str) -> str:  # type: ignore[override]
        if prompt_name is None:
            return ""
        if prompt_name == "missing.txt":
            raise FileNotFoundError("not found")
        if prompt_name and "system" in prompt_name:
            return self.system_prompt_text
        return self.prompt_text


class StubOllamaClient:
    def __init__(self):
        self.calls = []
        self.config = OllamaClientConfig(
            url="http://localhost:11434/api/generate",
            model="llama3:8b",
            csv_path=Path("unused.csv"),
            options=OllamaOptions(),
            timeout_seconds=180,
        )

    def generate(self, system_prompt: str, prompt: str, prompt_name: str | None = None, input_text: str | None = None):
        self.calls.append({"system": system_prompt, "prompt": prompt, "prompt_name": prompt_name, "input_text": input_text})
        return {
            "model": "llama3:8b",
            "response": "<http://example.org/s> <http://example.org/p> <http://example.org/o> .",
            "done": True,
        }


@pytest.fixture()
def client():
    repo = StubPromptRepo(prompt_text="Prompt content", system_prompt_text="System prompt content")
    service = KnowledgeGraphService(
        repo,
        default_prompt="test_prompt.txt",
        default_system_prompt="system_prompt.txt",
    )

    from flask import Flask

    app = Flask(__name__)
    app.register_blueprint(create_analyze_blueprint(service))
    app.config.update({"TESTING": True})

    with app.test_client() as client:
        yield client


def test_health_ok(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok"}


def test_analyze_happy_path(client):
    payload = {"text": "Some text", "prompt_name": "test_prompt.txt"}
    resp = client.post("/analyze", data=json.dumps(payload), content_type="application/json")

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["text"] == "Some text"
    assert data["rdf"] is None


def test_analyze_missing_text_returns_400(client):
    resp = client.post("/analyze", data=json.dumps({}), content_type="application/json")
    assert resp.status_code == 400
    assert "text" in resp.get_json()["error"]


def test_analyze_missing_prompt_returns_404(client):
    payload = {"text": "Other", "prompt_name": "missing.txt"}
    resp = client.post("/analyze", data=json.dumps(payload), content_type="application/json")

    assert resp.status_code == 404
    assert "not found" in resp.get_json()["error"]


def test_analyze_replaces_placeholder(client):
    repo = StubPromptRepo(prompt_text="Placeholder: ${USER_TEXT}", system_prompt_text="System prompt content")
    service = KnowledgeGraphService(
        repo,
        default_prompt="test_prompt.txt",
        default_system_prompt="system_prompt.txt",
    )

    from flask import Flask

    app = Flask(__name__)
    app.register_blueprint(create_analyze_blueprint(service))
    app.config.update({"TESTING": True})

    with app.test_client() as local_client:
        payload = {"text": "abc", "prompt_name": "test_prompt.txt"}
        resp = local_client.post("/analyze", data=json.dumps(payload), content_type="application/json")

        assert resp.status_code == 200
        assert resp.get_json()["text"] == "abc"
        assert resp.get_json()["rdf"] is None


def test_analyze_includes_generation_payload():
    repo = StubPromptRepo(prompt_text="Prompt content", system_prompt_text="System prompt content")
    ollama = StubOllamaClient()
    service = KnowledgeGraphService(
        repo,
        default_prompt="test_prompt.txt",
        default_system_prompt="system_prompt.txt",
        ollama_client=ollama,
    )

    from flask import Flask

    app = Flask(__name__)
    app.register_blueprint(create_analyze_blueprint(service))
    app.config.update({"TESTING": True})

    with app.test_client() as client:
        payload = {"text": "Some text", "prompt_name": "test_prompt.txt", "system_prompt_name": "system_prompt.txt"}
        resp = client.post("/analyze", data=json.dumps(payload), content_type="application/json")

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["text"] == "Some text"
        assert data["rdf"] == "<http://example.org/s> <http://example.org/p> <http://example.org/o> ."
        assert ollama.calls[0]["system"] == "System prompt content"


def test_analyze_returns_508_when_rdf_is_invalid():
    class InvalidOllamaClient(StubOllamaClient):
        def generate(self, system_prompt: str, prompt: str, prompt_name: str | None = None, input_text: str | None = None):
            self.calls.append({"system": system_prompt, "prompt": prompt, "prompt_name": prompt_name, "input_text": input_text})
            return {"model": "llama3:8b", "response": "not rdf", "done": True}

    repo = StubPromptRepo(prompt_text="Prompt content", system_prompt_text="System prompt content")
    ollama = InvalidOllamaClient()
    service = KnowledgeGraphService(
        repo,
        default_prompt="test_prompt.txt",
        default_system_prompt="system_prompt.txt",
        ollama_client=ollama,
    )

    from flask import Flask

    app = Flask(__name__)
    app.register_blueprint(create_analyze_blueprint(service))
    app.config.update({"TESTING": True})

    with app.test_client() as client:
        payload = {"text": "Some text", "max_rdf_attempts": 2}
        resp = client.post("/analyze", data=json.dumps(payload), content_type="application/json")

        assert resp.status_code == 508
        data = resp.get_json()
        assert data["error"] == "rdf parse errror"
        assert data["attempts"] == 2
        assert len(ollama.calls) == 2
