"""Exports sub-project 24's real round-trip fixture (Hans Muster taxpayer +
Erika Vertreter legal rep + Peter Steuer + Anna Vollmacht) as static JSON
for the OpenFASTER pipeline showcase. Reuses the real, already-tested
pipeline functions from generator/*.py -- this file only extracts and
structures real graph content for display (as real node/edge lists for the
canvas's Sigma.js/graphology graph views, or a real header/row pair for its
spreadsheet view), no new pipeline logic.
"""
from __future__ import annotations

import json
import os
import shutil

import lxml.etree as etree
from rdflib import Literal, Namespace, URIRef
from rdflib.namespace import RDF, RDFS

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


def _literal_node(predicate_qname: str, value) -> dict:
    return {"id": f"lit:{predicate_qname}|{value}", "label": f'"{value}"', "kind": "literal"}


def _excel_sheet() -> dict:
    return {
        "headers": ["Antrag-ID", "Role", "Anrede", "Vorname", "Nachname"],
        "row": ["A1", "STEUERPFLICHTIGE_PERSON", "HERR", "Hans", "Muster"],
    }


def _sso_graph(raw_graph) -> dict:
    personen_sheet = next(raw_graph.subjects(SSO.sheetName, Literal("Personen")))
    cell = next(
        c
        for c in raw_graph.objects(personen_sheet, SSO.hasCell)
        if int(raw_graph.value(c, SSO.rowIndex)) == 2 and int(raw_graph.value(c, SSO.columnIndex)) == 4
    )
    row_val = int(raw_graph.value(cell, SSO.rowIndex))
    col_val = int(raw_graph.value(cell, SSO.columnIndex))
    lit_val = str(raw_graph.value(cell, SSO.literalValue))

    cell_node = {"id": str(cell), "label": f"cell (row {row_val}, col {col_val})", "kind": "iri"}
    row_lit = _literal_node("sso:rowIndex", row_val)
    col_lit = _literal_node("sso:columnIndex", col_val)
    val_lit = _literal_node("sso:literalValue", lit_val)
    return {
        "nodes": [cell_node, row_lit, col_lit, val_lit],
        "edges": [
            {"source": cell_node["id"], "target": row_lit["id"], "label": "sso:rowIndex"},
            {"source": cell_node["id"], "target": col_lit["id"], "label": "sso:columnIndex"},
            {"source": cell_node["id"], "target": val_lit["id"], "label": "sso:literalValue"},
        ],
    }


def _abox_graph(abox_graph, structure_graph) -> dict:
    role = abox_graph.value(HANS_RECORD, OFR.hasRole)
    parent = abox_graph.value(HANS_RECORD, OFR.partOfRecord)
    obs = next(
        o
        for o in abox_graph.subjects(RDF.type, OFR.FieldObservation)
        if abox_graph.value(o, OFR.aboutRecord) == HANS_RECORD
        and abox_graph.value(o, OFR.observedConcept) == VORNAME_CONCEPT
    )
    value = str(abox_graph.value(obs, OFR.hasValue))
    role_label = str(structure_graph.value(role, RDFS.label))
    concept_label = str(structure_graph.value(VORNAME_CONCEPT, RDFS.label))

    person_node = {"id": str(HANS_RECORD), "label": "Hans Muster (person)", "kind": "iri"}
    antrag_node = {"id": str(parent), "label": "Erstattungsantrag A1", "kind": "iri"}
    role_node = {"id": str(role), "label": role_label, "kind": "iri"}
    obs_node = {"id": str(obs), "label": "Vorname observation", "kind": "iri"}
    concept_node = {"id": str(VORNAME_CONCEPT), "label": concept_label, "kind": "iri"}
    value_lit = _literal_node("ofr:hasValue", value)

    return {
        "nodes": [person_node, antrag_node, role_node, obs_node, concept_node, value_lit],
        "edges": [
            {"source": person_node["id"], "target": antrag_node["id"], "label": "ofr:partOfRecord"},
            {"source": person_node["id"], "target": role_node["id"], "label": "ofr:hasRole"},
            {"source": obs_node["id"], "target": person_node["id"], "label": "ofr:aboutRecord"},
            {"source": obs_node["id"], "target": concept_node["id"], "label": "ofr:observedConcept"},
            {"source": obs_node["id"], "target": value_lit["id"], "label": "ofr:hasValue"},
        ],
    }


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


def _xmlo_graph(xmlo_graph, elements) -> dict:
    leaf = _find_hans_vorname_xmlo_element(xmlo_graph, elements)
    element_node = {"id": str(leaf), "label": "Vorname element", "kind": "iri"}
    name_lit = _literal_node("xmlo:elementName", "Vorname")
    ns_lit = _literal_node("xmlo:namespaceURI", str(xmlo_graph.value(leaf, XMLO.namespaceURI)))
    text_lit = _literal_node("xmlo:textContent", "Hans")
    pos_lit = _literal_node("xmlo:childPosition", int(xmlo_graph.value(leaf, XMLO.childPosition)))
    return {
        "nodes": [element_node, name_lit, ns_lit, text_lit, pos_lit],
        "edges": [
            {"source": element_node["id"], "target": name_lit["id"], "label": "xmlo:elementName"},
            {"source": element_node["id"], "target": ns_lit["id"], "label": "xmlo:namespaceURI"},
            {"source": element_node["id"], "target": text_lit["id"], "label": "xmlo:textContent"},
            {"source": element_node["id"], "target": pos_lit["id"], "label": "xmlo:childPosition"},
        ],
    }


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


def _xml_snippet(instance) -> str:
    antraege_el = next(c for c in instance if etree.QName(c).localname == "Antraege")
    first_erstattungsantrag = next(iter(antraege_el))
    namespace = etree.QName(first_erstattungsantrag).namespace
    clean = _with_default_namespace(first_erstattungsantrag, namespace)
    return etree.tostring(clean, pretty_print=True).decode("utf-8").strip()


def export(output_path: str) -> None:
    structure = load_graph("modules/kafe.ttl")
    structure.parse("/work/institutional-ontology/institutional-ontology.owl", format="xml")
    layout = load_graph("layouts/kafe-canonical.ttl")

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
                {"id": "excel", "title": "Excel", "subtitle": "Personen sheet, row 2", "kind": "sheet", "sheet": _excel_sheet()},
                {"id": "sso", "title": "SSO graph", "subtitle": "extract_raw_cells", "kind": "graph", "graph": _sso_graph(raw)},
                {"id": "abox", "title": "A-box graph", "subtitle": "interpret_master_detail", "kind": "graph", "graph": _abox_graph(abox, structure)},
                {"id": "xmlo", "title": "XMLO graph", "subtitle": "generate_instance", "kind": "graph", "graph": _xmlo_graph(xmlo_graph, elements)},
                {"id": "xml", "title": "Real XML", "subtitle": "serialize_xmlo_to_xml", "kind": "text", "lang": "xml", "snippet": _xml_snippet(instance)},
            ],
        }
    finally:
        shutil.rmtree(fixture_dir, ignore_errors=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


if __name__ == "__main__":
    export(os.environ.get("SHOWCASE_OUTPUT", "showcase-pipeline-data.json"))
