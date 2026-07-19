# Prompt documentation

This service uses two prompt files to turn plain text into a compact RDF/Turtle knowledge graph:

- `prompt/system/knowledge_graph.txt`
- `prompt/prompts/few-shot.txt`

The system prompt defines the model's role and hard output constraints. The few-shot prompt defines the task, the allowed prefixes, examples, and the placeholder where request text is inserted.

## System prompt

File: `prompt/system/knowledge_graph.txt`

The system prompt tells the LLM to behave as a structured data assistant. Its main purpose is to reduce invalid output by repeating strict Turtle rules:

- return RDF/Turtle only;
- use only the prefixes declared in the user prompt;
- prefer `kg:` resources, classes, and predicates with snake_case local names;
- include `rdfs:label` with language tags for every subject or object resource;
- prefer entity-to-entity triples over literal-only descriptions so SPARQL evaluation can traverse to labeled answers;
- use `kg:is` for type and classification relationships;
- prefer a small stable predicate vocabulary when it fits the text: `kg:is`, `kg:of`, `kg:from`, `kg:in`, `kg:on`, `kg:to`, `kg:with`, `kg:has_part`, `kg:part_of`, `kg:located_in`, and `kg:instance_of`;
- finish every subject block with `.`;
- avoid markdown, prose, headings, and undeclared prefixes such as `schema:` or `ex:`;
- keep the graph concise so the output is more likely to be complete and parseable.

This prompt is loaded through `DEFAULT_SYSTEM_PROMPT_NAME`, which defaults to `system/knowledge_graph.txt`.

## Few-shot prompt

File: `prompt/prompts/few-shot.txt`

The few-shot prompt contains the task instructions sent as the user prompt. It has four important parts.

### 1. Task definition

The prompt starts by asking the model to transform an input `Text` into a knowledge graph using RDF/Turtle syntax. It also says the response must contain only RDF/Turtle, with no notes, headings, explanations, or markdown.

### 2. Formatting and vocabulary constraints

The prompt repeats constraints that make the generated RDF easier to parse:

- every subject block must end with a period;
- labels must use one pair of double quotes;
- labels must include language tags, for example `"Alan Turing"@en`;
- every entity, concept, class, place, person, organization, event, and object that appears as a subject or object must have an `rdfs:label`;
- generated RDF should prefer traversable entity-to-entity triples, because the evaluator uses label-based SPARQL queries to compare answers;
- generated resource names, classes, and predicates should use `kg:` with snake_case local names;
- type and classification relationships should use `kg:is`;
- relationship predicates should stay close to the shared vocabulary when possible: `kg:is`, `kg:of`, `kg:from`, `kg:in`, `kg:on`, `kg:to`, `kg:with`, `kg:has_part`, `kg:part_of`, `kg:located_in`, and `kg:instance_of`;
- undeclared prefixes are not allowed.

### 3. Allowed prefixes

The prompt declares the only prefixes the model may use:

```turtle
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix wd: <http://www.wikidata.org/entity/> .
@prefix kg: <https://example.org/wikidata-description/> .
```

The current examples mostly use `kg:` for generated entities and relations, and `rdfs:label` for readable labels. `wd:` is available when a prompt variant or future workflow wants to include Wikidata entity IRIs.

### 4. Examples and placeholder

The prompt includes three examples:

- a person, place, and event relation;
- an organization releasing an AI model;
- a scientific discovery involving people, a substance, and a place.

These examples show the expected graph style:

- one RDF subject block per entity;
- compact predicates such as `kg:worked_at`, `kg:released`, and `kg:discovered`;
- explicit entity classes such as `kg:Person`, `kg:Place`, and `kg:ChemicalSubstance`;
- labels for all resources that are used as subjects or objects;
- traversable links between labeled resources whenever the text supports them.

## Evaluation-oriented output

The generated RDF is later compared with dataset-derived SPARQL questions. Those queries are answer-oriented and use `rdfs:label` as the stable comparison surface instead of requiring the generated graph to reuse the exact same IRIs or predicates as the reference Turtle. For that reason, prompt changes should preserve:

- a labeled main entity from the input text;
- labeled answer entities or concepts;
- direct or short entity-to-entity paths from the main entity to likely answer entities;
- stable `kg:` predicates, especially `kg:is` for classification.

The final lines are:

```text
Text: ${USER_TEXT}
RDF:
```

At runtime, the service replaces `${USER_TEXT}` with the `text` field from the `/analyze` request. The model then completes the RDF after `RDF:`.

## Runtime behavior

When `/analyze` is called, the service:

1. loads the selected system prompt and few-shot prompt;
2. replaces `${USER_TEXT}` or `${Text_TEXT}` with the request text;
3. sends both prompts to Ollama `/api/generate` with `stream:false`;
4. extracts the RDF/Turtle part of the response;
5. tries small repairs for common formatting issues;
6. validates the result with `rdflib.Graph.parse(format="turtle")`;
7. asks the model to repair invalid Turtle when attempts remain.

The public API returns only:

```json
{
  "text": "<original request text>",
  "rdf": "<validated Turtle RDF>"
}
```

## Editing guidelines

When changing the prompt, keep these rules stable:

- keep `${USER_TEXT}` in the prompt unless you intentionally want the service to append the text as a chat-style `User:` turn;
- keep all prefixes declared in the prompt if examples use them;
- do not add examples that use undeclared prefixes;
- prefer smaller complete graphs over large graphs that may be truncated;
- include labels for every generated subject and object so downstream evaluation has a stable answer surface;
- prefer entity-to-entity relationships over storing important answers only as plain literals;
- keep type/classification examples aligned with `kg:is`;
- avoid expanding the predicate vocabulary unless the evaluation code and both KG generation prompts are updated together;
- keep examples syntactically valid Turtle, because the model tends to copy their structure.

Good prompt changes usually add clearer examples or stricter constraints without changing the response format. Risky changes include adding prose after `RDF:`, introducing new prefixes without declaring them, or asking for markdown/code fences.
