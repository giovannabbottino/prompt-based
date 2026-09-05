from typing import Any, Protocol, runtime_checkable
from uuid import uuid4

from ..domain.models import AnalyzeRequest, AnalyzeResponse
from ..domain.rdf_validation import extract_rdf_text, validate_rdf
from ..domain.structured_rdf import model_response_to_turtle
from ..infrastructure.prompt_repository import PromptRepository
from ..infrastructure.request_logger import RequestLogger


class GenerationClient(Protocol):
    def generate(
        self,
        system_prompt: str,
        prompt: str,
        prompt_name: str | None = None,
        input_text: str | None = None,
    ) -> dict[str, Any]: ...


@runtime_checkable
class HealthClient(Protocol):
    def health_check(self) -> dict[str, Any]: ...


class RDFValidationError(RuntimeError):
    def __init__(self, message: str, attempts: int, last_error: str | None = None) -> None:
        super().__init__(message)
        self.attempts = attempts
        self.last_error = last_error


class KnowledgeGraphService:
    def __init__(
        self,
        prompt_repository: PromptRepository,
        default_prompt: str,
        default_system_prompt: str,
        ollama_client: GenerationClient | None = None,
        request_logger: RequestLogger | None = None,
    ) -> None:
        self.prompt_repository = prompt_repository
        self.default_prompt = default_prompt
        self.default_system_prompt = default_system_prompt
        self.ollama_client = ollama_client
        self.request_logger = request_logger

    def analyze(self, request: AnalyzeRequest) -> AnalyzeResponse:
        key = request.idempotence_key or str(uuid4())
        self._log(key, "analyze_started", {"text": request.text})
        prompt_name = request.prompt_name or self.default_prompt
        system_prompt_name = request.system_prompt_name or self.default_system_prompt

        system_prompt_text = self.prompt_repository.load_prompt(system_prompt_name)
        prompt_text = self.prompt_repository.load_prompt(prompt_name)

        # Fill supported text placeholders; otherwise append user text in a chat-style turn.
        if "${USER_TEXT}" in prompt_text or "${Text_TEXT}" in prompt_text:
            message = prompt_text.replace("${USER_TEXT}", request.text).replace(
                "${Text_TEXT}", request.text
            )
        else:
            message = f"{prompt_text}\n\nUser: {request.text}\nAssistant:"

        generation_response = None
        if self.ollama_client:
            generation_response = self._generate_valid_rdf(
                system_prompt=system_prompt_text,
                prompt=message,
                prompt_name=prompt_name,
                input_text=request.text,
                max_attempts=request.max_rdf_attempts,
                key=key,
            )

        response = AnalyzeResponse(
            prompt_name=prompt_name,
            system_prompt_name=system_prompt_name,
            prompt=prompt_text,
            input_text=request.text,
            message_for_model=message,
            generation=generation_response,
        )
        self._log(
            key,
            "analyze_completed",
            {
                "prompt_name": prompt_name,
                "system_prompt_name": system_prompt_name,
                "rdf": str((generation_response or {}).get("response") or ""),
            },
        )
        return response

    def health_check(self) -> dict[str, Any] | None:
        if isinstance(self.ollama_client, HealthClient):
            return self.ollama_client.health_check()
        return None

    def _generate_valid_rdf(
        self,
        system_prompt: str,
        prompt: str,
        prompt_name: str,
        input_text: str,
        max_attempts: int,
        key: str,
    ) -> dict[str, Any]:
        client = self.ollama_client
        if client is None:
            raise RuntimeError("A generation client is required to generate RDF.")

        attempts = max(1, min(int(max_attempts or 3), 3))
        current_prompt = prompt
        last_error: str | None = None

        for attempt in range(1, attempts + 1):
            self._log(
                key,
                "llm_rdf_request",
                {"attempt": attempt, "prompt_name": prompt_name, "prompt": current_prompt},
            )
            generation = client.generate(
                system_prompt=system_prompt,
                prompt=current_prompt,
                prompt_name=prompt_name,
                input_text=input_text,
            )
            self._log(
                key,
                "llm_rdf_response",
                {"attempt": attempt, "response": str(generation.get("response") or "")},
            )

            model_response = str(generation.get("response") or "")
            try:
                rdf_text = model_response_to_turtle(model_response)
                self._parse_rdf(rdf_text)
                generation["response"] = rdf_text
                generation["rdf_validation_attempts"] = attempt
                self._log(
                    key,
                    "rdf_validated",
                    {"attempt": attempt, "validation_method": "strict"},
                )
                return generation
            except Exception as exc:  # rdflib raises parser-specific exception classes.
                last_error = str(exc)
                self._log(
                    key,
                    "rdf_validation_failed",
                    {"attempt": attempt, "error": last_error},
                )

            if attempt == attempts:
                break
            current_prompt = self._build_retry_prompt(
                prompt, model_response, last_error or "Invalid structured RDF response."
            )

        raise RDFValidationError(
            "RDF parsing failed.",
            attempts=attempts,
            last_error=last_error,
        )

    @staticmethod
    def _parse_rdf(rdf_text: str) -> None:
        validate_rdf(rdf_text)

    @staticmethod
    def _extract_rdf_text(response_text: str) -> str:
        return extract_rdf_text(response_text)

    @staticmethod
    def _build_retry_prompt(original_prompt: str, invalid_response: str, parser_error: str) -> str:
        error = parser_error[:1200]
        previous = invalid_response[:6000]
        return (
            f"{original_prompt}\n\n"
            "The previous structured RDF JSON could not be converted to RDF.\n"
            f"Validation error:\n{error}\n\n"
            "Return the complete corrected JSON object using the required triples schema. "
            "Every triple needs subject, predicate, object, and object_type. Return JSON only, "
            "without Turtle, markdown, comments, or explanations.\n"
            f"Previous invalid response:\n{previous}"
        )

    def _log(self, key: str, event: str, payload: dict[str, Any]) -> None:
        if self.request_logger:
            self.request_logger.log(idempotence_key=key, event=event, payload=payload)
