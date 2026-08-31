# Prompt documentation

The prompt-based service uses this pair:

- `prompt/system/knowledge_graph.txt`
- `prompt/prompts/few-shot.txt`

The same core instructions and few-shot examples are used by the ontology-based service. The ontology variant adds only its Wikidata-grounding block.

## System prompt

The system prompt assigns the model the role `RDF knowledge graph engineer`. It defines the non-negotiable output contract:

- return only RDF/Turtle;
- follow RDF 1.1 Turtle syntax strictly;
- use `;` between different predicates for the same subject;
- use `,` only between multiple objects of the same predicate;
- end every statement with `.`;
- never leave a predicate without an object;
- declare every prefix in the same response before using it;
- include the exact `kg:` declaration whenever a `kg:` name is used;
- never place two objects next to each other without Turtle punctuation;
- label every resource with `rdfs:label` and a language tag;
- never invent a Wikidata QID.

Valid Turtle syntax takes precedence over every other instruction or example. The complete model response must parse with `rdflib.Graph.parse(format="turtle")`.

## Few-shot prompt

The default user prompt is intentionally generic. It asks the model to represent the entities, concepts, and relationships stated in any input text without imposing a domain-specific ontology or a long fixed predicate vocabulary.

It declares four available prefixes:

```turtle
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix wd: <http://www.wikidata.org/entity/> .
@prefix kg: <https://example.org/wikidata-description/> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
```

The prompt-based service does not query Wikidata. A `wd:Q...` resource may be used only when the model is confident that the QID is reliable; otherwise it must use a descriptive `kg:` resource.

## Few-shot examples

Both baseline prompts contain the same two compact examples:

1. a person managing a research laboratory located in Lisbon;
2. a mango classified as a fruit.

Together they demonstrate:

- labeled resources connected by explicit relationships;
- `;` between different predicates for one subject;
- `.` at the end of every statement;
- a concise classification relation using `kg:is`.

The examples deliberately use local `kg:` resources. This prevents an example QID from being mistaken for evidence about a later request. Unit tests extract both example documents and parse them with RDFLib.

## Current input marker

Examples are enclosed in `<EXAMPLES>`. The request text is isolated in:

```text
<CURRENT_TEXT>
Text:
${USER_TEXT}
</CURRENT_TEXT>

RDF/Turtle:
```

At runtime, `${USER_TEXT}` is replaced by the `text` field sent to `/analyze`. The legacy `${Text_TEXT}` marker remains supported for custom prompts. If neither marker exists, the service appends the input as a user turn.

## Runtime validation and retry

After Ollama answers, the service removes only response wrappers and validates the candidate strictly with RDFLib. An invalid candidate is sent back to the same generation stage with the parser error and the core Turtle separator rules. The service performs no local syntax repair, statement salvage, or substitute graph generation.

## Editing guidelines

- Keep the prompt core aligned with `ontology-based`.
- Keep the two example transformations identical in both projects.
- Keep `${USER_TEXT}` inside `<CURRENT_TEXT>`.
- Keep example Turtle self-contained and parseable.
- Keep the shared mandatory syntax block identical in all three pipelines.
- Keep prefix binding and the distinction between `;`, `,`, and `.` explicit.
- Do not introduce undeclared prefixes or domain-specific requirements into the shared core.
- Add ontology-specific grounding only to the ontology prompt's dedicated Wikidata block.
- Update `tests/unit/test_prompts.py` whenever the prompt contract or examples change.
