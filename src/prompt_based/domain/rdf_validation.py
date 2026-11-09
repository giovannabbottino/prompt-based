import json

from rdflib import Graph
from rdflib.namespace import RDFS

RDF_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {"rdf": {"type": "string", "minLength": 1}},
    "required": ["rdf"],
    "additionalProperties": False,
}


def parse_rdf_response(response_text: str) -> str:
    """Extract Turtle from the model's JSON object without repairing its output."""
    payload = json.loads(response_text)
    if not isinstance(payload, dict) or set(payload) != {"rdf"}:
        raise ValueError("Model response must be a JSON object containing only the 'rdf' field.")
    rdf = payload["rdf"]
    if not isinstance(rdf, str) or not rdf.strip():
        raise ValueError("Model response field 'rdf' must be a non-empty string.")
    return rdf.strip()


def validate_rdf(rdf_text: str) -> None:
    if not rdf_text.strip():
        raise ValueError("Empty RDF response.")
    graph = Graph().parse(data=rdf_text, format="turtle")
    if len(graph) == 0:
        raise ValueError("RDF response contains no triples.")
    if not any(predicate != RDFS.label for _, predicate, _ in graph):
        raise ValueError("RDF response contains labels but no semantic relationships.")
