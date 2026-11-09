import pytest

from prompt_based.domain.rdf_validation import parse_rdf_response, validate_rdf


def test_strict_validation_rejects_predicate_after_comma():
    with pytest.raises(Exception, match="Bad syntax"):
        validate_rdf(
            "@prefix kg: <https://example.org/kg/> .\n"
            "kg:java kg:is kg:language, kg:allows kg:portable_code ."
        )


def test_strict_validation_accepts_objects_then_new_predicate():
    validate_rdf(
        "@prefix kg: <https://example.org/kg/> .\n"
        "kg:java kg:is kg:language, kg:object_oriented_language ; "
        "kg:allows kg:portable_code ."
    )


@pytest.mark.parametrize(
    "rdf",
    [
        "",
        "@prefix kg: <https://example.org/kg/> .",
        '<https://example.org/a> <http://www.w3.org/2000/01/rdf-schema#label> "A" .',
    ],
)
def test_rejects_empty_graphs_and_labels_without_relationships(rdf):
    with pytest.raises(ValueError):
        validate_rdf(rdf)


@pytest.mark.parametrize(
    "response",
    [
        "{}",
        "[]",
        "null",
        '{"triples": []}',
        '{"rdf": null}',
        '{"rdf": 1}',
        '{"rdf": []}',
        '{"rdf": "  "}',
        '{"rdf": "x", "extra": true}',
        '```json\n{"rdf": "x"}\n```',
        "not JSON",
    ],
)
def test_model_response_requires_only_a_nonempty_rdf_string(response):
    with pytest.raises(ValueError):
        parse_rdf_response(response)
