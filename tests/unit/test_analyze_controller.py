import requests
from flask import Flask

from prompt_based.controllers.analyze_controller import create_analyze_blueprint
from prompt_based.domain.models import AnalyzeRequest, AnalyzeResponse


class StubService:
    def __init__(self, health_status: str = "ok", error: Exception | None = None) -> None:
        self.health_status = health_status
        self.error = error

    def health_check(self):
        return {"status": self.health_status}

    def analyze(self, request: AnalyzeRequest) -> AnalyzeResponse:
        if self.error is not None:
            raise self.error
        raise AssertionError("analyze() was not expected in this test")


def _client(service: StubService):
    app = Flask(__name__)
    app.register_blueprint(create_analyze_blueprint(service))
    return app.test_client()


def test_health_returns_503_when_ollama_is_unavailable() -> None:
    response = _client(StubService(health_status="unavailable")).get("/health")

    assert response.status_code == 503
    assert response.get_json()["ollama"]["status"] == "unavailable"


def test_analyze_returns_504_for_external_timeout() -> None:
    response = _client(StubService(error=requests.Timeout("model timed out"))).post(
        "/analyze",
        json={"text": "Mango is a fruit."},
    )

    assert response.status_code == 504
    assert response.get_json() == {
        "error": "External service request timed out.",
        "details": "model timed out",
    }


def test_rejects_non_object_json_body() -> None:
    response = _client(StubService()).post("/analyze", json=["not", "an", "object"])

    assert response.status_code == 400
    assert response.get_json() == {"error": "Request body must be a JSON object."}
