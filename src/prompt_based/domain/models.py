from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AnalyzeRequest:
    text: str
    idempotence_key: str | None = None
    prompt_name: str | None = None
    system_prompt_name: str | None = None
    max_rdf_attempts: int = 3


@dataclass(frozen=True)
class AnalyzeResponse:
    input_text: str
    generation: dict[str, Any]
