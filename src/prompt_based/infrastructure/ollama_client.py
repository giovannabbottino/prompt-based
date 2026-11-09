from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import requests
from requests import Response

from ..domain.rdf_validation import RDF_RESPONSE_SCHEMA


def _env_value(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    if value in (None, ""):
        return default
    # Accept accidental inline comments in local .env files, e.g. FOO=1# note.
    value = value.split("#", 1)[0].strip()
    return value or default


def _int_from_env(name: str) -> int | None:
    value = _env_value(name)
    if value in (None, ""):
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _float_from_env(name: str) -> float | None:
    value = _env_value(name)
    if value in (None, ""):
        return None
    try:
        return float(value)
    except ValueError:
        return None


@dataclass(frozen=True)
class OllamaOptions:
    seed: int | None = None
    temperature: float | None = None
    top_k: int | None = None
    top_p: float | None = None
    min_p: float | None = None
    num_predict: int | None = None

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if self.seed is not None:
            payload["seed"] = self.seed
        if self.temperature is not None:
            payload["temperature"] = self.temperature
        if self.top_k is not None:
            payload["top_k"] = self.top_k
        if self.top_p is not None:
            payload["top_p"] = self.top_p
        if self.min_p is not None:
            payload["min_p"] = self.min_p
        if self.num_predict is not None:
            payload["num_predict"] = self.num_predict
        return payload


@dataclass(frozen=True)
class OllamaClientConfig:
    url: str
    model: str
    options: OllamaOptions
    timeout_seconds: int

    @classmethod
    def from_env(cls) -> OllamaClientConfig:
        url = _env_value("OLLAMA_API_URL", "http://localhost:11434") or "http://localhost:11434"
        model = _env_value("OLLAMA_MODEL", "llama3.1:8b") or "llama3.1:8b"
        options = OllamaOptions(
            seed=_int_from_env("OLLAMA_SEED"),
            temperature=_float_from_env("OLLAMA_TEMPERATURE"),
            top_k=_int_from_env("OLLAMA_TOP_K"),
            top_p=_float_from_env("OLLAMA_TOP_P"),
            min_p=_float_from_env("OLLAMA_MIN_P"),
            num_predict=_int_from_env("OLLAMA_NUM_PREDICT"),
        )
        return cls(
            url=url,
            model=model,
            options=options,
            timeout_seconds=_int_from_env("OLLAMA_TIMEOUT_SECONDS") or 180,
        )


class OllamaClient:
    """
    Thin HTTP client for Ollama's generation and health endpoints.
    """

    def __init__(self, config: OllamaClientConfig):
        self.config = config

    def generate(
        self,
        system_prompt: str,
        prompt: str,
    ) -> dict[str, Any]:
        base_url = self.config.url.rstrip("/")
        target_url = base_url if base_url.endswith("/api/generate") else f"{base_url}/api/generate"

        payload: dict[str, Any] = {
            "model": self.config.model,
            "system": system_prompt,
            "prompt": prompt,
            # Disable streaming to ensure we receive a single JSON object we can log.
            "stream": False,
            "format": RDF_RESPONSE_SCHEMA,
        }
        options_payload = self.config.options.to_payload()
        if options_payload:
            payload["options"] = options_payload

        response = requests.post(target_url, json=payload, timeout=self.config.timeout_seconds)
        if getattr(response, "status_code", None) == 404:
            detail = self._response_detail(response)
            raise RuntimeError(
                f"Ollama model '{self.config.model}' is not available. "
                f"Run: ollama pull {self.config.model}. Details: {detail}"
            )
        response.raise_for_status()
        return self._parse_response(response)

    def health_check(self) -> dict[str, Any]:
        base_url = self.config.url.rstrip("/")
        target_url = base_url if base_url.endswith("/api/tags") else f"{base_url}/api/tags"
        try:
            response = requests.get(target_url, timeout=5)
            response.raise_for_status()
            data = response.json()
        except Exception as exc:  # pragma: no cover - defensive guard
            return {"status": "unavailable", "details": str(exc)}

        models = data.get("models", [])
        model_names = {
            model.get("name") or model.get("model") for model in models if isinstance(model, dict)
        }
        if self.config.model not in model_names:
            return {
                "status": "missing_model",
                "model": self.config.model,
                "details": f"Run: ollama pull {self.config.model}",
            }
        return {"status": "ok", "model": self.config.model}

    def _response_detail(self, response: Response) -> str:
        try:
            data = response.json()
        except ValueError:
            return response.text.strip()
        if isinstance(data, dict):
            return str(data.get("error") or data)
        return str(data)

    def _parse_response(self, response: Response) -> dict[str, Any]:
        try:
            data = response.json()
        except ValueError as exc:  # pragma: no cover - defensive guard
            raise RuntimeError("Invalid JSON response from generation API") from exc
        if not isinstance(data, dict) or not isinstance(data.get("response"), str):
            raise RuntimeError("Generation API response must contain a string response field")
        return data
