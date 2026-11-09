import json
import re
from pathlib import Path

import pytest
from rdflib import Graph, URIRef
from rdflib.namespace import RDFS

from prompt_based.domain.rdf_validation import validate_rdf

REQUIRED_PREFIXES = (
    "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n"
    "@prefix wd: <http://www.wikidata.org/entity/> .\n"
    "@prefix kg: <https://example.org/wikidata-description/> .\n"
)


@pytest.mark.parametrize(
    ("index", "expected_relationships"),
    [
        (
            0,
            [
                ("nelson_mandela", "participated_in", "presidential_inauguration"),
                ("presidential_inauguration", "took_place_in", "pretoria"),
            ],
        ),
        (
            1,
            [
                ("openai", "developed", "gpt_3"),
                ("gpt_3", "application_domain", "natural_language_processing"),
            ],
        ),
        (
            2,
            [
                ("radium_discovery", "discovered_by", "marie_curie"),
                ("radium_discovery", "discovered_by", "pierre_curie"),
                ("radium_discovery", "substance", "radium"),
                ("radium_discovery", "took_place_in", "paris"),
            ],
        ),
    ],
)
def test_user_prompt_has_three_valid_examples(index, expected_relationships):
    prompt = Path("prompt/prompts/few-shot.txt").read_text(encoding="utf-8")
    assert "Return JSON only" in prompt
    assert 'exactly one key: "rdf"' in prompt
    assert "QID" in prompt
    assert prompt.count("${USER_TEXT}") == 1
    examples = re.findall(r"Example response:\n(.*?)(?=\nExample text:|\nText:)", prompt, re.S)
    assert len(examples) == 3
    payload = json.loads(examples[index])
    assert set(payload) == {"rdf"}
    assert payload["rdf"].startswith(REQUIRED_PREFIXES)
    validate_rdf(payload["rdf"])
    graph = Graph().parse(data=payload["rdf"], format="turtle")
    kg = "https://example.org/wikidata-description/"
    for subject, predicate, obj in expected_relationships:
        assert (URIRef(kg + subject), URIRef(kg + predicate), URIRef(kg + obj)) in graph
    resources = set(graph.subjects()) | {obj for obj in graph.objects() if isinstance(obj, URIRef)}
    for resource in resources:
        assert (resource, RDFS.label, None) in graph


def test_system_prompt_assigns_role_and_requires_turtle():
    prompt = Path("prompt/system/knowledge_graph.txt").read_text(encoding="utf-8")
    assert prompt.startswith("Role: You are a knowledge graph extraction engineer.")
    assert 'JSON object with only the "rdf" key' in prompt
    assert "Do not return a triples array" in prompt
    assert "prefix declaration" in prompt
    for declaration in REQUIRED_PREFIXES.splitlines():
        assert declaration in prompt
