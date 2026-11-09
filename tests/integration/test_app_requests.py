import json
from pathlib import Path

import pytest
from rdflib import Graph, URIRef

from prompt_based.app import create_app
from prompt_based.infrastructure import prompt_repository


@pytest.fixture()
def ollama_mock(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    captured = {}
    sample_response = {
        "model": "llama3.1:8b",
        "created_at": "2024-01-01T00:00:00Z",
        "response": json.dumps(
            {
                "rdf": (
                    "@prefix kg: <https://example.org/wikidata-description/> .\n"
                    "kg:subject kg:related_to kg:object ."
                )
            }
        ),
        "thinking": "analysis",
        "done": True,
        "done_reason": "stop",
        "total_duration": 100,
        "load_duration": 10,
        "prompt_eval_count": 11,
        "prompt_eval_duration": 12,
        "eval_count": 13,
        "eval_duration": 14,
        "logprobs": [],
    }

    def fake_post(url, json=None, **kwargs):  # type: ignore[override]
        captured["url"] = url
        captured["payload"] = json

        class DummyResponse:
            def raise_for_status(self) -> None:
                return None

            def json(self):
                return sample_response

        return DummyResponse()

    log_path = tmp_path / "ollama.jsonl"
    monkeypatch.setenv("OLLAMA_JSONL_PATH", str(log_path))
    monkeypatch.setenv("ANALYZE_LOG_PATH", str(tmp_path / "analyze.jsonl"))
    monkeypatch.setattr("prompt_based.infrastructure.ollama_client.requests.post", fake_post)

    return captured, sample_response, log_path


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, ollama_mock):
    captured, sample_response, log_path = ollama_mock

    prompt_dir = tmp_path / "prompt"
    prompt_dir.mkdir()
    (prompt_dir / "test_prompt.txt").write_text("Prompt content", encoding="utf-8")
    (prompt_dir / "system_prompt.txt").write_text("System prompt content", encoding="utf-8")

    repo_original_init = prompt_repository.PromptRepository.__init__

    def _init(self, prompt_dir=None, _default_dir=prompt_dir):
        chosen_dir = _default_dir if prompt_dir is None else prompt_dir
        repo_original_init(self, prompt_dir=chosen_dir)

    monkeypatch.setattr(prompt_repository.PromptRepository, "__init__", _init)
    monkeypatch.setenv("DEFAULT_PROMPT_NAME", "test_prompt.txt")
    monkeypatch.setenv("DEFAULT_SYSTEM_PROMPT_NAME", "system_prompt.txt")
    monkeypatch.setenv("OLLAMA_API_URL", "http://localhost:11434")
    monkeypatch.setenv("OLLAMA_MODEL", "llama3.1:8b")

    app = create_app()
    app.config.update({"TESTING": True})

    with app.test_client() as client:
        yield client, captured, sample_response, log_path


def test_analyze_request_flow(client):
    client, capture, sample_response, log_path = client
    payload = {
        "text": "Integration text",
        "prompt_name": "test_prompt.txt",
        "system_prompt_name": "system_prompt.txt",
    }
    resp = client.post("/analyze", data=json.dumps(payload), content_type="application/json")

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["text"] == "Integration text"
    graph = Graph().parse(data=data["rdf"], format="turtle")
    assert (
        URIRef("https://example.org/wikidata-description/subject"),
        URIRef("https://example.org/wikidata-description/related_to"),
        URIRef("https://example.org/wikidata-description/object"),
    ) in graph

    assert "Integration text" in capture["payload"]["prompt"]
    assert capture["payload"]["format"]["required"] == ["rdf"]
    assert data["rdf"] == json.loads(sample_response["response"])["rdf"]

    assert log_path.exists()
    entries = [json.loads(line) for line in log_path.read_text().splitlines()]
    assert len(entries) == 1
    payload = entries[0]["payload"]
    assert payload["rdf_valid"] is True
    assert payload["generation"] == sample_response
    assert payload["rdf"] == data["rdf"]
    assert payload["input_text"] == "Integration text"


def test_analyze_placeholder_is_replaced(
    ollama_mock, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    captured, sample_response, log_path = ollama_mock
    prompt_dir = tmp_path / "prompt2"
    prompt_dir.mkdir()
    (prompt_dir / "test_prompt.txt").write_text("Placeholder ${USER_TEXT}", encoding="utf-8")
    (prompt_dir / "system_prompt.txt").write_text("System prompt content", encoding="utf-8")

    repo_original_init = prompt_repository.PromptRepository.__init__

    def _init(self, prompt_dir=None, _default_dir=prompt_dir):
        chosen_dir = _default_dir if prompt_dir is None else prompt_dir
        repo_original_init(self, prompt_dir=chosen_dir)

    monkeypatch.setattr(prompt_repository.PromptRepository, "__init__", _init)
    monkeypatch.setenv("DEFAULT_PROMPT_NAME", "test_prompt.txt")
    monkeypatch.setenv("DEFAULT_SYSTEM_PROMPT_NAME", "system_prompt.txt")
    monkeypatch.setenv("OLLAMA_API_URL", "http://localhost:11434")
    monkeypatch.setenv("OLLAMA_MODEL", "llama3.1:8b")

    app = create_app()
    app.config.update({"TESTING": True})
    with app.test_client() as client2:
        payload = {
            "text": "XYZ",
            "prompt_name": "test_prompt.txt",
            "system_prompt_name": "system_prompt.txt",
        }
        resp = client2.post("/analyze", data=json.dumps(payload), content_type="application/json")

        assert resp.status_code == 200
        assert resp.get_json()["text"] == "XYZ"
        assert "kg:subject kg:related_to kg:object" in resp.get_json()["rdf"]


def test_analyze_rejects_triples_array(client):
    client, _, sample_response, log_path = client
    sample_response["response"] = json.dumps({"triples": []})
    response = client.post("/analyze", json={"text": "Hello", "max_rdf_attempts": 1})
    assert response.status_code == 422
    assert response.get_json()["attempts"] == 1
    entry = json.loads(log_path.read_text())
    assert entry["payload"]["rdf_valid"] is False
