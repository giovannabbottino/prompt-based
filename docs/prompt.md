# Prompt behavior

The prompt-based pipeline asks Ollama for structured RDF triples rather than Turtle syntax. The
bundled client sends the same JSON Schema used by the hybrid and ontology pipelines through
Ollama's `format` field.

## Model response

The model returns one object with a non-empty `triples` array:

```json
{
  "triples": [
    {
      "subject": "kg:alice",
      "predicate": "rdfs:label",
      "object": "Alice",
      "object_type": "literal",
      "language": "en"
    },
    {
      "subject": "kg:alice",
      "predicate": "kg:manages",
      "object": "kg:research_laboratory",
      "object_type": "resource"
    }
  ]
}
```

Every item requires `subject`, `predicate`, `object`, and `object_type`. Literal objects may have
either `language` or `datatype`. Supported identifiers use `wd:`, `kg:`, `rdf:`, `rdfs:`, `xsd:`,
or `owl:`. Bare resource names and unsafe `kg:` local names are normalized deterministically.

## RDF construction

The application validates the structured response, converts every item into an RDFLib term, adds
the triples to an `rdflib.Graph`, binds the known namespaces, and calls
`graph.serialize(format="turtle")`. The API therefore continues to return RDF/Turtle as a string,
but the model is no longer responsible for Turtle punctuation or prefix declarations.

The serialized result must contain at least one semantic relationship in addition to labels. If
structured validation fails, the model receives the validation error and its previous response and
may retry up to `max_rdf_attempts`.

## Editing guidelines

- Keep `${USER_TEXT}` in the user prompt.
- Keep the structured fields identical across all three pipelines.
- Keep labels mandatory for resource subjects and objects.
- Keep `object_type` restricted to `resource` and `literal`.
- Keep the application serializer authoritative for final Turtle syntax.
