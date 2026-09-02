"""Exports sub-project 24's real round-trip fixture (Hans Muster taxpayer +
Erika Vertreter legal rep + Peter Steuer + Anna Vollmacht) as static JSON
for the OpenFASTER pipeline showcase. Reuses the real, already-tested
pipeline functions from generator/*.py -- this file only extracts and
structures real graph content for display, no new pipeline logic (the
generic RDF-dump logic itself lives in generator/rdf_graph_dump.py, not
here, since it's real reusable machinery, not export-specific structuring).
"""
from __future__ import annotations

import json
import os
import shutil

import lxml.etree as etree
from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF

from generator.rdf_graph_dump import dump_graph, node_id
from generator.showcase_fixture import build_fixture_workbook
from generator.xlsx_ingest import extract_raw_cells, interpret_master_detail
from generator.xml_instance_generator import generate_instance, serialize_xmlo_to_xml
from generator.xsd_generator import load_graph

KAFE = "https://openfaster.org/kafe/schema#"
KAFE_NS = Namespace(KAFE)
OFR = Namespace("https://openfaster.org/realizations/schema#")
SSO = Namespace("https://purl.openfaster.org/sso/")
XMLO = Namespace("https://purl.openfaster.org/xmlo/")
IO = "https://purl.openfaster.org/io/IO_"
ANTRAEGE_SHEET = f"{KAFE}ErstAntragSheet"
ID_COLUMN = f"{KAFE}ErstAntragIdColumn"
PERSONEN_SHEET = f"{KAFE}PersonenSheet"
PARENT_KEY_COLUMN = f"{KAFE}PersonenParentIdColumn"
ROLE_COLUMN = f"{KAFE}PersonenRoleColumn"

# Personen sheet row 2 -- Hans Muster, taxpayer on Erstattungsantrag A1
HANS_RECORD = URIRef("urn:record:person:2")
VORNAME_CONCEPT = URIRef(f"{IO}0000001")

# Real .owl sources for the four architecture-layer nodes that have one --
# sibling repo clones on this box, same convention this file already used
# for institutional-ontology.owl below.
_ONTOLOGY_OWL_PATHS = {
    "spreadsheet-ontology": "/work/spreadsheet-ontology/spreadsheet-ontology.owl",
    "institutional-ontology": "/work/institutional-ontology/institutional-ontology.owl",
    "xml-ontology": "/work/xml-ontology/xml-ontology.owl",
    "xsd-ontology": "/work/xsd-ontology/xsd-ontology.owl",
}


def _sheets_from_raw(raw_graph) -> list[dict]:
    """Derives every real sheet's headers + full data rows directly from
    the raw cell graph -- row 1 of each sheet is already the real header
    text the generated workbook itself carries (verified live: e.g.
    Personen's real header row reads "Zugehörige Antrag-ID"/"Person role"/
    "Form of address"/"All given names"/"Last name", not the simplified
    "Antrag-ID"/"Role"/"Anrede"/"Vorname"/"Nachname" this export used to
    hand-type -- a real, previously-unnoticed mismatch this fixes as a
    side effect of deriving sheets from the real data instead of
    duplicating it by hand).
    """
    sheet_nodes = sorted(
        raw_graph.subjects(SSO.sheetName, None),
        key=lambda s: int(raw_graph.value(s, SSO.sheetPosition)),
    )
    sheets = []
    for sheet in sheet_nodes:
        name = str(raw_graph.value(sheet, SSO.sheetName))
        cells = list(raw_graph.objects(sheet, SSO.hasCell))
        max_col = max(int(raw_graph.value(c, SSO.columnIndex)) for c in cells)
        by_row: dict[int, dict[int, str]] = {}
        for cell in cells:
            row_idx = int(raw_graph.value(cell, SSO.rowIndex))
            col_idx = int(raw_graph.value(cell, SSO.columnIndex))
            by_row.setdefault(row_idx, {})[col_idx] = str(raw_graph.value(cell, SSO.literalValue))
        row_indices = sorted(by_row)
        header_row = row_indices[0]
        headers = [by_row[header_row].get(col, "") for col in range(1, max_col + 1)]
        data_rows = [
            [by_row[r].get(col, "") for col in range(1, max_col + 1)]
            for r in row_indices[1:]
        ]
        sheets.append({"name": name, "headers": headers, "rows": data_rows})
    return sheets


def _hans_vorname_cell_id(raw_graph) -> str:
    personen_sheet = next(raw_graph.subjects(SSO.sheetName, Literal("Personen")))
    cell = next(
        c
        for c in raw_graph.objects(personen_sheet, SSO.hasCell)
        if int(raw_graph.value(c, SSO.rowIndex)) == 2 and int(raw_graph.value(c, SSO.columnIndex)) == 4
    )
    return node_id(cell)


def _hans_vorname_observation_id(abox_graph) -> str:
    obs = next(
        o
        for o in abox_graph.subjects(RDF.type, OFR.FieldObservation)
        if abox_graph.value(o, OFR.aboutRecord) == HANS_RECORD
        and abox_graph.value(o, OFR.observedConcept) == VORNAME_CONCEPT
    )
    return node_id(obs)


def _find_hans_vorname_xmlo_element(xmlo_graph, elements):
    antraege = next(el for el in elements if str(xmlo_graph.value(el, XMLO.elementName)) == "Antraege")
    erstattungsantraege = list(xmlo_graph.objects(antraege, XMLO.hasChildElement))
    for erstattungsantrag in erstattungsantraege:
        for allg in xmlo_graph.objects(erstattungsantrag, XMLO.hasChildElement):
            if str(xmlo_graph.value(allg, XMLO.elementName)) != "AllgAngaben":
                continue
            for stpfl in xmlo_graph.objects(allg, XMLO.hasChildElement):
                if str(xmlo_graph.value(stpfl, XMLO.elementName)) != "SteuerpflichtigePerson":
                    continue
                for natp_wrap in xmlo_graph.objects(stpfl, XMLO.hasChildElement):
                    for natp in xmlo_graph.objects(natp_wrap, XMLO.hasChildElement):
                        for leaf in xmlo_graph.objects(natp, XMLO.hasChildElement):
                            if (
                                str(xmlo_graph.value(leaf, XMLO.elementName)) == "Vorname"
                                and str(xmlo_graph.value(leaf, XMLO.textContent)) == "Hans"
                            ):
                                return leaf
    raise ValueError("Hans's Vorname XMLO element not found")


def _with_default_namespace(el, namespace: str):
    """Rebuild `el` (and its real children) under a fresh tree that
    declares `namespace` as the default (unprefixed) namespace, so the
    showcase's pretty-printed snippet reads as real KaFE XML normally
    would (xmlns declared once, no per-element ns0: prefix clutter) --
    same real tags/text/namespace, just re-rooted for clean display.
    """
    tag = etree.QName(el).localname
    new_el = etree.Element(f"{{{namespace}}}{tag}", nsmap={None: namespace})
    if el.text:
        new_el.text = el.text
    for child in el:
        new_el.append(_with_default_namespace(child, namespace))
    return new_el


def _xml_snippet_full(instance) -> str:
    """The full real document: every real top-level element
    serialize_xmlo_to_xml produced (Antraege, containing both real
    Erstattungsantrag entries, plus the submission-level
    BevollmaechtigtePerson) -- `instance` itself is a synthetic <instance>
    wrapper (see serialize_xmlo_to_xml's own docstring), not real KaFE XML,
    so each real child is re-rooted and serialized on its own rather than
    picking just the first Erstattungsantrag.
    """
    parts = []
    for child in instance:
        namespace = etree.QName(child).namespace
        clean = _with_default_namespace(child, namespace)
        parts.append(etree.tostring(clean, pretty_print=True).decode("utf-8").strip())
    return "\n".join(parts)


def _architecture_graphs(kafe_module_graph) -> dict:
    graphs = {"realizations": dump_graph(kafe_module_graph, structural_only=False)}
    for repo_id, path in _ONTOLOGY_OWL_PATHS.items():
        g = Graph()
        g.parse(path, format="xml")
        graphs[repo_id] = dump_graph(g, structural_only=True)
    return graphs


def export(output_path: str) -> None:
    structure = load_graph("modules/kafe.ttl")
    structure.parse("/work/institutional-ontology/institutional-ontology.owl", format="xml")
    layout = load_graph("layouts/kafe-canonical.ttl")
    # A separate, unmerged load of kafe.ttl alone -- the architecture
    # node's own graph must be exactly this real curated module (274
    # triples / 81 subjects, checked live), not `structure` above, which
    # additionally merges in institutional-ontology's own triples.
    kafe_module_graph = load_graph("modules/kafe.ttl")

    # A fixed, stable directory (not tempfile.TemporaryDirectory()'s random
    # name) so extract_raw_cells' path-derived cell URIs -- and therefore
    # this export's own output -- are reproducible across runs, not noisy
    # git diffs on every refresh.
    fixture_dir = "/tmp/openfaster-showcase-fixture"
    shutil.rmtree(fixture_dir, ignore_errors=True)
    os.makedirs(fixture_dir, exist_ok=True)
    try:
        xlsx_path = build_fixture_workbook(structure, layout, fixture_dir)
        raw = extract_raw_cells(xlsx_path)
        submission = URIRef("urn:record:submission:1")
        abox = interpret_master_detail(
            raw, layout, ANTRAEGE_SHEET, ID_COLUMN, PERSONEN_SHEET, PARENT_KEY_COLUMN, ROLE_COLUMN, structure, submission
        )
        xmlo_graph, elements = generate_instance(structure, KAFE_NS.KAFE_CType, abox, submission)
        instance = serialize_xmlo_to_xml(xmlo_graph, elements)

        data = {
            "meta": {
                "source": "realizations v0.3.0, tests/test_round_trip.py fixture",
                "highlightedValue": {
                    "field": "Vorname",
                    "value": "Hans",
                    "person": "Hans Muster (taxpayer, Erstattungsantrag A1)",
                },
            },
            "stages": [
                {"id": "excel", "title": "Excel", "subtitle": "Personen + Erstattungsantraege sheets", "kind": "sheet", "sheets": _sheets_from_raw(raw)},
                {"id": "sso", "title": "SSO graph", "subtitle": "extract_raw_cells", "kind": "graph", "graph": dump_graph(raw), "highlightId": _hans_vorname_cell_id(raw)},
                {"id": "abox", "title": "A-box graph", "subtitle": "interpret_master_detail", "kind": "graph", "graph": dump_graph(abox), "highlightId": _hans_vorname_observation_id(abox)},
                {"id": "xmlo", "title": "XMLO graph", "subtitle": "generate_instance", "kind": "graph", "graph": dump_graph(xmlo_graph), "highlightId": node_id(_find_hans_vorname_xmlo_element(xmlo_graph, elements))},
                {"id": "xml", "title": "Real XML", "subtitle": "serialize_xmlo_to_xml", "kind": "text", "lang": "xml", "snippet": _xml_snippet_full(instance)},
            ],
            "architectureGraphs": _architecture_graphs(kafe_module_graph),
        }
    finally:
        shutil.rmtree(fixture_dir, ignore_errors=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


if __name__ == "__main__":
    export(os.environ.get("SHOWCASE_OUTPUT", "showcase-pipeline-data.json"))
