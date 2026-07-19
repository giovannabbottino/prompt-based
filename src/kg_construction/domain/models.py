from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AnalyzeRequest:
    text: str
    prompt_name: str | None = None
    system_prompt_name: str | None = None
    max_rdf_attempts: int = 3


@dataclass(frozen=True)
class AnalyzeResponse:
    prompt_name: str
    system_prompt_name: str
    prompt: str
    input_text: str
    message_for_model: str
    generation: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "prompt_name": self.prompt_name,
            "system_prompt_name": self.system_prompt_name,
            "prompt": self.prompt,
            "input_text": self.input_text,
            "message_for_model": self.message_for_model,
            "generation": self.generation,
        }
