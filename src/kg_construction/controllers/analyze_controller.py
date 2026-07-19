import requests
from flask import Blueprint, Response, jsonify, request

from ..application.services import KnowledgeGraphService, RDFValidationError
from ..domain.models import AnalyzeRequest


def create_analyze_blueprint(service: KnowledgeGraphService) -> Blueprint:
    blueprint = Blueprint("analyze", __name__)

    @blueprint.route("/health", methods=["GET"])
    def health() -> tuple[Response, int]:
        payload: dict[str, object] = {"status": "ok"}
        ollama_health = service.health_check()
        if ollama_health is not None:
            payload["ollama"] = ollama_health
        return jsonify(payload), 200

    @blueprint.route("/analyze", methods=["POST"])
    def analyze() -> tuple[Response, int]:
        data = request.get_json(silent=True) or {}
        if not isinstance(data, dict):
            return jsonify({"error": "Request body must be a JSON object."}), 400
        text = data.get("text")
        if not isinstance(text, str) or not text.strip():
            return jsonify({"error": "Field 'text' is required."}), 400

        prompt_name = data.get("prompt_name")
        system_prompt_name = data.get("system_prompt_name")
        max_rdf_attempts = data.get("max_rdf_attempts", 3)
        if not isinstance(max_rdf_attempts, int) or isinstance(max_rdf_attempts, bool):
            return jsonify({"error": "Field 'max_rdf_attempts' must be an integer."}), 400
        if prompt_name is not None and not isinstance(prompt_name, str):
            return jsonify({"error": "Field 'prompt_name' must be a string."}), 400
        if system_prompt_name is not None and not isinstance(system_prompt_name, str):
            return jsonify({"error": "Field 'system_prompt_name' must be a string."}), 400

        try:
            response = service.analyze(
                AnalyzeRequest(
                    text=text,
                    prompt_name=prompt_name,
                    system_prompt_name=system_prompt_name,
                    max_rdf_attempts=max_rdf_attempts,
                )
            )
        except FileNotFoundError as exc:
            return jsonify({"error": str(exc)}), 404
        except requests.RequestException as exc:
            return jsonify(
                {"error": "Failed to generate response from model.", "details": str(exc)}
            ), 502
        except RDFValidationError as exc:
            return jsonify(
                {
                    "error": "RDF parsing failed.",
                    "attempts": exc.attempts,
                    "details": exc.last_error,
                }
            ), 422
        except RuntimeError as exc:
            return jsonify({"error": str(exc)}), 502
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        rdf_output: object | None = None
        if response.generation:
            rdf_output = response.generation.get("response")

        return jsonify({"text": response.input_text, "rdf": rdf_output}), 200

    return blueprint
