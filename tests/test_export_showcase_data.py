"""Confirms the showcase export produces the full real fixture at every
pipeline stage, plus a real per-repo ontology/module graph for the
architecture layer -- not placeholders, and not narrowed to one value.
"""
import json
import os

from scripts.export_showcase_data import export


def test_export_produces_the_full_real_fixture_at_every_stage(tmp_path):
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

    # Excel: both real sheets, every real row -- headers come from the
    # real generated workbook's own header row, not a hand-typed guess.
    excel = by_id["excel"]
    assert excel["kind"] == "sheet"
    sheets_by_name = {s["name"]: s for s in excel["sheets"]}
    assert set(sheets_by_name) == {"Erstattungsantraege", "Personen"}
    assert sheets_by_name["Erstattungsantraege"]["headers"] == ["Antrag-ID"]
    assert sheets_by_name["Erstattungsantraege"]["rows"] == [["A1"], ["A2"]]
    personen = sheets_by_name["Personen"]
    assert personen["headers"] == [
        "Zugehörige Antrag-ID", "Person role", "Form of address", "All given names", "Last name",
    ]
    assert personen["rows"] == [
        ["A1", "STEUERPFLICHTIGE_PERSON", "HERR", "Hans", "Muster"],
        ["A1", "GESETZLICHE_VERTRETUNG", "FRAU", "Erika", "Vertreter"],
        ["A2", "STEUERPFLICHTIGE_PERSON", "HERR", "Peter", "Steuer"],
        ["", "BEVOLLMAECHTIGTE_PERSON", "FRAU", "Anna", "Vollmacht"],
    ]

    # SSO/A-box/XMLO: full real graphs (all 4 people, both antraege), real
    # identifiers as labels, a real highlightId naming an actual node.
    for stage_id in ("sso", "abox", "xmlo"):
        stage = by_id[stage_id]
        assert stage["kind"] == "graph"
        node_ids = {n["id"] for n in stage["graph"]["nodes"]}
        assert all(n["kind"] in ("iri", "blank", "literal") for n in stage["graph"]["nodes"])
        for edge in stage["graph"]["edges"]:
            assert edge["source"] in node_ids
            assert edge["target"] in node_ids
        assert stage["highlightId"] in node_ids
        # Real, not a friendly gloss: every non-literal node's label is its own id.
        for n in stage["graph"]["nodes"]:
            if n["kind"] in ("iri", "blank"):
                assert n["label"] == n["id"]
        literal_labels = [n["label"] for n in stage["graph"]["nodes"] if n["kind"] == "literal"]
        assert any("Hans" in label for label in literal_labels)
        assert any("Peter" in label for label in literal_labels)  # full fixture, not just Hans

    # Real XML: the full document -- both Erstattungsantrag entries plus
    # the submission-level BevollmaechtigtePerson (Anna).
    xml_snippet = by_id["xml"]["snippet"]
    assert by_id["xml"]["kind"] == "text"
    assert xml_snippet.count("<Erstattungsantrag") == 2
    assert "<Vorname>Hans</Vorname>" in xml_snippet
    assert "<Vorname>Peter</Vorname>" in xml_snippet
    assert "BevollmaechtigtePerson" in xml_snippet
    assert "Anna" in xml_snippet

    # Architecture layer: a real graph per repo, not prose.
    arch_graphs = data["architectureGraphs"]
    assert set(arch_graphs) == {
        "spreadsheet-ontology", "institutional-ontology", "realizations", "xml-ontology", "xsd-ontology",
    }
    for repo_id, graph in arch_graphs.items():
        assert graph["nodes"], f"{repo_id} produced an empty graph"
        assert graph["edges"], f"{repo_id} produced no edges"
    # spreadsheet-ontology's real Cell class, by its real rdfs:label
    sso_labels = {n["label"] for n in arch_graphs["spreadsheet-ontology"]["nodes"]}
    assert "Cell" in sso_labels
    # realizations shows the real curated kafe.ttl module, not its own tiny vocabulary
    assert len(arch_graphs["realizations"]["nodes"]) > 20
