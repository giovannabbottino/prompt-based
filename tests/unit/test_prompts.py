from pathlib import Path


def test_user_prompt_requires_structured_rdf_json():
    prompt = Path("prompt/prompts/few-shot.txt").read_text(encoding="utf-8")

    assert "structured RDF triples" in prompt
    assert '"triples"' in prompt
    assert '"subject"' in prompt
    assert '"predicate"' in prompt
    assert '"object_type"' in prompt
    assert "Return JSON only" in prompt
    assert "Do not return RDF/Turtle" in prompt
    assert "QID" in prompt
    assert "${USER_TEXT}" in prompt
    assert "Alice manages a research laboratory in Lisbon." in prompt


def test_system_prompt_assigns_role_and_delegates_turtle_serialization():
    prompt = Path("prompt/system/knowledge_graph.txt").read_text(encoding="utf-8")

    assert prompt.startswith("Role: You are a knowledge graph extraction engineer.")
    assert "Return exactly one JSON object" in prompt
    assert "converts these triples to RDF/Turtle with rdflib" in prompt
    assert "Return JSON only" in prompt
    assert "object_type" in prompt
