# Prompts

[README](../README.md) · [API](analyze.md) · [Testing](how-to-test.md)

## Templates

[System prompt](../prompt/system/knowledge_graph.txt) defines extraction rules; [Few-shot template](../prompt/prompts/few-shot.txt) provides three examples and the `${USER_TEXT}` placeholder. The examples cover a person, a place, and a historical event; an organization, an AI model, and its application domain; and a scientific discovery, people, a substance, and a place. Select the default templates in `.env`.

## Output contract

The model must return exactly one JSON object with an `rdf` string:

```json
{"rdf": "@prefix kg: <https://example.org/wikidata-description/> .\nkg:alice kg:knows kg:bob ."}
```

## Validation and retries

The client sends a schema requiring this shape. The service decodes the JSON and validates the Turtle once with RDFLib before logging. Empty RDF and graphs containing only labels fail validation. The RDF is returned with outer whitespace trimmed, without syntax repair or reserialization. Syntax validation does not verify factual accuracy.

When editing prompts, keep `${USER_TEXT}`, require complete Turtle prefix declarations, labels for resources, and relationships supported by the source text. Use descriptive `kg:` identifiers when a Wikidata QID is uncertain. Escape quotes and newlines in the JSON string. Extra keys, triples arrays, Markdown fences, and prose are rejected.

The prefixes and resource labels requested by the templates are prompt instructions; the validator checks JSON shape, Turtle syntax, non-empty content, and a relationship beyond labels, without enforcing those prefixes or labels. Invalid output receives feedback, up to three total attempts.
