"""Confirms the showcase export produces real Hans Muster data at every
pipeline stage -- not placeholders, not fabricated strings.
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
    assert "Hans" in by_id["excel"]["snippet"]
    assert by_id["sso"]["snippet"].count('"Hans"') == 1
    assert "ofr:hasRole" in by_id["abox"]["snippet"]
    assert "Hans" in by_id["abox"]["snippet"]
    assert "xmlo:elementName" in by_id["xmlo"]["snippet"]
    assert "Hans" in by_id["xmlo"]["snippet"]
    assert "<Vorname>Hans</Vorname>" in by_id["xml"]["snippet"]
    assert "<Nachname>Muster</Nachname>" in by_id["xml"]["snippet"]
