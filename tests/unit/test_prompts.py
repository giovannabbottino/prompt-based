from pathlib import Path

from rdflib import Graph


def _mandatory_turtle_rules(prompt: str) -> str:
    return prompt.split("Mandatory Turtle syntax rules:\n", 1)[1].split("\n\n", 1)[0]


def _example_rdf_documents(prompt: str) -> list[str]:
    examples = prompt.split("<EXAMPLES>", 1)[1].split("</EXAMPLES>", 1)[0]
    documents = []
    for section in examples.split("RDF/Turtle:\n")[1:]:
        documents.append(section.split("\n\nText:\n", 1)[0].strip())
    return documents


def test_user_prompt_is_generic_and_requires_strict_turtle():
    prompt = Path("prompt/prompts/few-shot.txt").read_text(encoding="utf-8")

    assert "Convert the text below into a knowledge graph" in prompt
    assert "Follow RDF 1.1 Turtle syntax strictly" in prompt
    assert "Use `;` to continue the same subject with a different predicate" in prompt
    assert "Use `,` only to separate multiple objects of the same predicate" in prompt
    assert 'rdflib.Graph.parse(format="turtle")' in prompt
    assert "Never invent a QID" in prompt
    assert "${USER_TEXT}" in prompt
    assert "<EXAMPLES>" in prompt
    assert "Alice manages a research laboratory in Lisbon." in prompt
    assert "A mango is a fruit." in prompt
    assert 'wd:Q597 rdfs:label "Lisbon"@en' in prompt
    assert 'wd:Q169 rdfs:label "mango"@en' in prompt
    assert 'kg:is wd:Q3314483' in prompt
    assert "<CURRENT_TEXT>" in prompt


def test_few_shot_examples_are_valid_turtle():
    prompt = Path("prompt/prompts/few-shot.txt").read_text(encoding="utf-8")
    documents = _example_rdf_documents(prompt)

    assert len(documents) == 2
    assert all(len(Graph().parse(data=document, format="turtle")) > 0 for document in documents)


def test_system_prompt_assigns_role_and_enforces_turtle_only_output():
    prompt = Path("prompt/system/knowledge_graph.txt").read_text(encoding="utf-8")

    assert prompt.startswith("Role: You are an RDF knowledge graph engineer.")
    assert "Follow RDF 1.1 Turtle syntax strictly" in prompt
    assert "Use `;` to continue the same subject with a different predicate" in prompt
    assert "Use `,` only to separate multiple objects of the same predicate" in prompt
    assert "Return only RDF/Turtle" in prompt
    assert "Valid Turtle syntax takes precedence" in prompt


def test_user_and_system_prompts_share_mandatory_turtle_rules():
    user_prompt = Path("prompt/prompts/few-shot.txt").read_text(encoding="utf-8")
    system_prompt = Path("prompt/system/knowledge_graph.txt").read_text(encoding="utf-8")
    rules = _mandatory_turtle_rules(user_prompt)

    assert rules == _mandatory_turtle_rules(system_prompt)
    assert "Every prefix used in a triple MUST be declared" in rules
    assert "include exactly `@prefix kg:" in rules
    assert "Never write two objects next to each other" in rules
    assert "Use `,` only to separate multiple objects of the same predicate" in rules
    assert "Use `;` to continue the same subject with a different predicate" in rules
