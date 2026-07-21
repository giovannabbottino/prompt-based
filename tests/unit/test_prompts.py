from pathlib import Path


def test_few_shot_prompt_requires_wikidata_ids_and_text_labels():
    prompt = Path("prompt/prompts/few-shot.txt").read_text(encoding="utf-8")

    assert "exact Wikidata resource `wd:Q...`" in prompt
    assert "The QID must appear as the subject or object" in prompt
    assert "never invent a QID" in prompt
    assert "exact human-readable surface form from the input Text" in prompt
    assert "wd:Q7251" in prompt
    assert "wd:Q7186" in prompt


def test_system_prompt_preserves_known_qids_and_surface_labels():
    prompt = Path("prompt/system/knowledge_graph.txt").read_text(encoding="utf-8")

    assert "exact `wd:Q...` Wikidata resource" in prompt
    assert "Never invent a QID" in prompt
    assert "exact human-readable surface form from the input text" in prompt
