from typing import Any, Protocol, runtime_checkable
from uuid import uuid4

from ..domain.models import AnalyzeRequest, AnalyzeResponse
from ..domain.rdf_validation import parse_rdf_response, validate_rdf
from ..infrastructure.prompt_repository import PromptRepository
from ..infrastructure.request_logger import RequestLogger


class GenerationClient(Protocol):
    def generate(
        self,
        system_prompt: str,
        prompt: str,
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
        ollama_client: GenerationClient,
        request_logger: RequestLogger | None = None,
        generation_logger: RequestLogger | None = None,
    ) -> None:
        self.prompt_repository = prompt_repository
        self.default_prompt = default_prompt
        self.default_system_prompt = default_system_prompt
        self.ollama_client = ollama_client
        self.request_logger = request_logger
        self.generation_logger = generation_logger

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
                "rdf": generation_response["response"],
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
        attempts = max(1, min(max_attempts, 3))
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
            )

            model_response = str(generation.get("response") or "")
            rdf_text = None
            last_error = None
            try:
                rdf_text = parse_rdf_response(model_response)
                validate_rdf(rdf_text)
            except Exception as exc:  # rdflib raises parser-specific exception classes.
                last_error = str(exc)

            if self.generation_logger:
                self.generation_logger.log(
                    idempotence_key=key,
                    event="llm_rdf_response",
                    payload={
                        "attempt": attempt,
                        "prompt_name": prompt_name,
                        "input_text": input_text,
                        "generation": generation,
                        "rdf_valid": last_error is None,
                        "rdf_note": last_error or "",
                        "rdf": rdf_text if last_error is None else None,
                    },
                )

            if last_error is None:
                self._log(
                    key,
                    "rdf_validated",
                    {"attempt": attempt, "validation_method": "strict"},
                )
                return {**generation, "response": rdf_text, "rdf_validation_attempts": attempt}

            self._log(
                key,
                "rdf_validation_failed",
                {"attempt": attempt, "error": last_error},
            )

            if attempt == attempts:
                break
            current_prompt = self._build_retry_prompt(
                prompt, model_response, last_error or "Invalid JSON/RDF response."
            )

        raise RDFValidationError(
            "RDF parsing failed.",
            attempts=attempts,
            last_error=last_error,
        )

    @staticmethod
    def _build_retry_prompt(original_prompt: str, invalid_response: str, parser_error: str) -> str:
        error = parser_error[:1200]
        previous = invalid_response[:6000]
        return (
            f"{original_prompt}\n\n"
            "The previous JSON/RDF response failed validation.\n"
            f"Validation error:\n{error}\n\n"
            'Return exactly one JSON object with only the "rdf" key. Its value must be a string '
            "containing the complete corrected RDF graph in Turtle syntax, with all required "
            "prefix declarations and at least one semantic relationship. Escape newlines and "
            "quotes correctly inside the JSON string. "
            "Do not include Markdown fences or explanations.\n"
            f"Previous invalid response:\n{previous}"
        )

    def _log(self, key: str, event: str, payload: dict[str, Any]) -> None:
        if self.request_logger:
            self.request_logger.log(idempotence_key=key, event=event, payload=payload)
