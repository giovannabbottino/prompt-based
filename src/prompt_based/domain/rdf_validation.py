from rdflib import Graph
from rdflib.namespace import RDFS


def extract_rdf_text(response_text: str) -> str:
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


def validate_rdf(rdf_text: str) -> None:
    if not rdf_text.strip():
        raise ValueError("Empty RDF response.")
    graph = Graph().parse(data=rdf_text, format="turtle")
    if len(graph) == 0:
        raise ValueError("RDF response contains no triples.")
    if not any(predicate != RDFS.label for _, predicate, _ in graph):
        raise ValueError("RDF response contains labels but no semantic relationships.")


def rdf_validation_result(response_text: str) -> tuple[bool, str]:
    try:
        validate_rdf(extract_rdf_text(response_text))
    except Exception as exc:  # rdflib raises parser-specific exception classes.
        return False, str(exc)
    return True, ""
