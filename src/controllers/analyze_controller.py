from flask import Blueprint, jsonify, request
import requests

from ..application.services import KnowledgeGraphService, RDFValidationError
from ..domain.models import AnalyzeRequest


def create_analyze_blueprint(service: KnowledgeGraphService) -> Blueprint:
    blueprint = Blueprint("analyze", __name__)

    @blueprint.route("/health", methods=["GET"])
    def health() -> tuple:
        payload = {"status": "ok"}
        if service.ollama_client:
            payload["ollama"] = service.ollama_client.health_check()
        return jsonify(payload), 200

    @blueprint.route("/analyze", methods=["POST"])
    def analyze() -> tuple:
        data = request.get_json(silent=True) or {}
        text = data.get("text")
        if not text:
            return jsonify({"error": "Field 'text' is required."}), 400

        prompt_name = data.get("prompt_name")
        system_prompt_name = data.get("system_prompt_name")
        max_rdf_attempts = data.get("max_rdf_attempts", 3)

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
            return jsonify({"error": "Failed to generate response from model.", "details": str(exc)}), 502
        except RDFValidationError as exc:
            return jsonify({"error": "rdf parse errror", "attempts": exc.attempts, "details": exc.last_error}), 508
        except RuntimeError as exc:
            return jsonify({"error": str(exc)}), 502
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        rdf_output = None
        if response.generation and isinstance(response.generation, dict):
            rdf_output = response.generation.get("response")

        return jsonify({"text": response.input_text, "rdf": rdf_output}), 200

    return blueprint
