"""Confirms the showcase export produces real Hans Muster data at every
pipeline stage -- as structured graph node/edge lists for the canvas's
real graph views, or a real header/row pair for its spreadsheet view, not
placeholders.
"""
import json
import os

from scripts.export_showcase_data import export


def test_export_produces_real_hans_muster_data_at_every_stage(tmp_path):
    output_path = os.path.join(tmp_path, "showcase-pipeline-data.json")
    export(output_path)

    with open(output_path, encoding="utf-8") as f:
        data = json.load(f)

    assert data["meta"]["highlightedValue"] == {
        "field": "Vorname",
        "value": "Hans",
        "person": "Hans Muster (taxpayer, Erstattungsantrag A1)",
    }

    stage_ids = [s["id"] for s in data["stages"]]
    assert stage_ids == ["excel", "sso", "abox", "xmlo", "xml"]
    by_id = {s["id"]: s for s in data["stages"]}

    # Excel: a real sheet (headers + one real data row), not text
    assert by_id["excel"]["kind"] == "sheet"
    assert by_id["excel"]["sheet"]["headers"] == ["Antrag-ID", "Role", "Anrede", "Vorname", "Nachname"]
    assert by_id["excel"]["sheet"]["row"] == ["A1", "STEUERPFLICHTIGE_PERSON", "HERR", "Hans", "Muster"]

    # SSO/A-box/XMLO: real node/edge graphs, gold-literal/blue-IRI kind
    # distinction the frontend needs, not pre-formatted text
    for stage_id in ("sso", "abox", "xmlo"):
        stage = by_id[stage_id]
        assert stage["kind"] == "graph"
        node_ids = {n["id"] for n in stage["graph"]["nodes"]}
        assert all(n["kind"] in ("iri", "literal") for n in stage["graph"]["nodes"])
        for edge in stage["graph"]["edges"]:
            assert edge["source"] in node_ids
            assert edge["target"] in node_ids
        literal_labels = [n["label"] for n in stage["graph"]["nodes"] if n["kind"] == "literal"]
        assert any("Hans" in label for label in literal_labels)

    assert by_id["abox"]["graph"]["nodes"]
    role_labels = [n["label"] for n in by_id["abox"]["graph"]["nodes"]]
    assert "Taxpayer" in role_labels

    # Real XML stays text -- it's the one stage that isn't itself a graph
    assert by_id["xml"]["kind"] == "text"
    assert "<Vorname>Hans</Vorname>" in by_id["xml"]["snippet"]
    assert "<Nachname>Muster</Nachname>" in by_id["xml"]["snippet"]
