from unittest.mock import Mock

import pytest

from prompt_based.domain.rdf_validation import RDF_RESPONSE_SCHEMA
from prompt_based.infrastructure.ollama_client import (
    OllamaClient,
    OllamaClientConfig,
    OllamaOptions,
)


def make_client():
    return OllamaClient(
        OllamaClientConfig(
            url="http://ollama:11434",
            model="llama3.1:8b",
            options=OllamaOptions(seed=42),
            timeout_seconds=30,
        )
    )


def test_client_requests_rdf_json_and_returns_raw_response_without_rdf_processing(monkeypatch):
    raw = {"response": "invalid RDF from model", "eval_count": 15}
    response = Mock()
    response.json.return_value = raw
    post = Mock(return_value=response)
    monkeypatch.setattr("prompt_based.infrastructure.ollama_client.requests.post", post)

    assert make_client().generate(system_prompt="System", prompt="Text") is raw
    response.raise_for_status.assert_called_once()
    post.assert_called_once_with(
        "http://ollama:11434/api/generate",
        json={
            "model": "llama3.1:8b",
            "system": "System",
            "prompt": "Text",
            "stream": False,
            "format": RDF_RESPONSE_SCHEMA,
            "options": {"seed": 42},
        },
        timeout=30,
    )


@pytest.mark.parametrize("payload", [[], None, {}, {"response": 42}])
def test_client_rejects_invalid_api_envelopes(monkeypatch, payload):
    response = Mock()
    response.json.return_value = payload
    monkeypatch.setattr(
        "prompt_based.infrastructure.ollama_client.requests.post", Mock(return_value=response)
    )
    with pytest.raises(RuntimeError, match="string response field"):
        make_client().generate(system_prompt="System", prompt="Text")


def test_env_config_forwards_only_supported_llm_settings(monkeypatch):
    settings = {
        "OLLAMA_SEED": "0",
        "OLLAMA_TEMPERATURE": "0",
        "OLLAMA_TOP_K": "40",
        "OLLAMA_TOP_P": "0.9",
        "OLLAMA_MIN_P": "0.05",
        "OLLAMA_NUM_PREDICT": "1536",
        "OLLAMA_TIMEOUT_SECONDS": "300",
        "OLLAMA_STOP": "ignored",
        "OLLAMA_NUM_CTX": "8192",
    }
    for name, value in settings.items():
        monkeypatch.setenv(name, value)
    response = Mock()
    response.json.return_value = {"response": '{"rdf": "example"}'}
    post = Mock(return_value=response)
    monkeypatch.setattr("prompt_based.infrastructure.ollama_client.requests.post", post)

    client = OllamaClient(OllamaClientConfig.from_env())
    client.generate(system_prompt="System", prompt="Text")

    assert post.call_args.kwargs["timeout"] == 300
    assert post.call_args.kwargs["json"]["options"] == {
        "seed": 0,
        "temperature": 0.0,
        "top_k": 40,
        "top_p": 0.9,
        "min_p": 0.05,
        "num_predict": 1536,
    }
