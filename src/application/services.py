import re
from typing import Optional

from rdflib import Graph

from ..domain.models import AnalyzeRequest, AnalyzeResponse
from ..infrastructure.ollama_client import OllamaClient
from ..infrastructure.prompt_repository import PromptRepository


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
        ollama_client: Optional[OllamaClient] = None,
    ) -> None:
        self.prompt_repository = prompt_repository
        self.default_prompt = default_prompt
        self.default_system_prompt = default_system_prompt
        self.ollama_client = ollama_client

    def analyze(self, request: AnalyzeRequest) -> AnalyzeResponse:
        prompt_name = request.prompt_name or self.default_prompt
        system_prompt_name = request.system_prompt_name or self.default_system_prompt

        system_prompt_text = self.prompt_repository.load_prompt(system_prompt_name)
        prompt_text = self.prompt_repository.load_prompt(prompt_name)

        # Fill supported text placeholders; otherwise append user text in a chat-style turn.
        if "${USER_TEXT}" in prompt_text or "${Text_TEXT}" in prompt_text:
            message = prompt_text.replace("${USER_TEXT}", request.text).replace("${Text_TEXT}", request.text)
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
            )

        return AnalyzeResponse(
            prompt_name=prompt_name,
            system_prompt_name=system_prompt_name,
            prompt=prompt_text,
            input_text=request.text,
            message_for_model=message,
            generation=generation_response,
        )

    def get_default_prompt(self) -> str:
        return self.default_prompt

    def get_default_system_prompt(self) -> str:
        return self.default_system_prompt

    def _generate_valid_rdf(
        self,
        system_prompt: str,
        prompt: str,
        prompt_name: str,
        input_text: str,
        max_attempts: int,
    ) -> dict:
        attempts = max(1, min(int(max_attempts or 3), 3))
        current_prompt = prompt
        last_error = None

        for attempt in range(1, attempts + 1):
            generation = self.ollama_client.generate(
                system_prompt=system_prompt,
                prompt=current_prompt,
                prompt_name=prompt_name,
                input_text=input_text,
            )

            rdf_text = self._extract_rdf_text(str(generation.get("response") or ""))
            for repair_method, candidate_rdf in self._rdf_repair_candidates(rdf_text):
                try:
                    self._parse_rdf(candidate_rdf)
                    generation["response"] = candidate_rdf
                    generation["rdf_validation_attempts"] = attempt
                    generation["rdf_repair_method"] = repair_method
                    return generation
                except Exception as exc:  # rdflib raises parser-specific exception classes.
                    last_error = str(exc)

            if attempt == attempts:
                break
            current_prompt = self._build_retry_prompt(prompt, rdf_text, last_error or "Invalid Turtle RDF.")

        raise RDFValidationError(
            "rdf parse errror",
            attempts=attempts,
            last_error=last_error,
        )

    @staticmethod
    def _parse_rdf(rdf_text: str) -> None:
        if not rdf_text.strip():
            raise ValueError("Empty RDF response.")
        Graph().parse(data=rdf_text, format="turtle")

    @staticmethod
    def _extract_rdf_text(response_text: str) -> str:
        text = response_text.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if lines and lines[0].strip().startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines).strip()

        rdf_markers = ("@prefix", "@base", "PREFIX", "BASE", "<", "_:")
        starts = [idx for marker in rdf_markers if (idx := text.find(marker)) >= 0]
        if starts:
            text = text[min(starts) :].strip()
        return text

    @classmethod
    def _rdf_repair_candidates(cls, rdf_text: str):
        raw = (rdf_text or "").strip().replace("\r\n", "\n").replace("\r", "\n")
        raw = raw.replace("\u201c", '"').replace("\u201d", '"').replace("\u2019", "'")
        raw = re.sub(r'""([^"\n]+)""', r'"\1"', raw)

        seen = set()

        def emit(method: str, value: str):
            value = (value or "").strip()
            if not value or value in seen:
                return
            seen.add(value)
            yield method, value

        yield from emit("trim", raw)

        if raw and not raw.endswith("."):
            yield from emit("append_final_dot", raw + " .")

        lines = raw.splitlines()
        last_complete_line = None
        for idx, line in enumerate(lines):
            if line.strip().endswith("."):
                last_complete_line = idx
        if last_complete_line is not None:
            yield from emit("keep_through_last_complete_statement", "\n".join(lines[: last_complete_line + 1]))

        blocks = re.split(r"\n\s*\n", raw)
        while len(blocks) > 1:
            blocks = blocks[:-1]
            candidate = "\n\n".join(blocks).strip()
            if candidate and not candidate.endswith("."):
                candidate += " ."
            yield from emit("drop_incomplete_last_block", candidate)

    @staticmethod
    def _build_retry_prompt(original_prompt: str, invalid_rdf: str, parser_error: str) -> str:
        error = parser_error[:1200]
        previous = invalid_rdf[:6000]
        return (
            f"{original_prompt}\n\n"
            "The previous answer was not valid Turtle RDF when parsed with rdflib Graph.parse.\n"
            f"Parser error:\n{error}\n\n"
            "Return only corrected valid Turtle RDF. Do not include markdown fences, comments, or explanations.\n"
            f"Previous invalid RDF:\n{previous}"
        )
