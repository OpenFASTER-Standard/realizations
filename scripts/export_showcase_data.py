"""Exports sub-project 24's real round-trip fixture (Hans Muster taxpayer +
Erika Vertreter legal rep + Peter Steuer + Anna Vollmacht) as static JSON
for the OpenFASTER pipeline showcase. Reuses the real, already-tested
pipeline functions from generator/*.py -- this file only extracts and
formats real graph content for display, no new pipeline logic.
"""
from __future__ import annotations

import json
import os
import shutil

import lxml.etree as etree
from rdflib import Literal, Namespace, URIRef
from rdflib.namespace import RDF

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


def _excel_snippet() -> str:
    return (
        "Antrag-ID | Role                    | Anrede | Vorname | Nachname\n"
        "A1        | STEUERPFLICHTIGE_PERSON | HERR   | Hans    | Muster"
    )


def _sso_snippet(raw_graph) -> str:
    personen_sheet = next(raw_graph.subjects(SSO.sheetName, Literal("Personen")))
    for cell in raw_graph.objects(personen_sheet, SSO.hasCell):
        if int(raw_graph.value(cell, SSO.rowIndex)) == 2 and int(raw_graph.value(cell, SSO.columnIndex)) == 4:
            return (
                f"<{cell}>\n"
                f'    sso:rowIndex {raw_graph.value(cell, SSO.rowIndex)} ;\n'
                f'    sso:columnIndex {raw_graph.value(cell, SSO.columnIndex)} ;\n'
                f'    sso:literalValue "{raw_graph.value(cell, SSO.literalValue)}" .'
            )
    raise ValueError("Hans's Vorname cell not found in the raw SSO graph")


def _abox_snippet(abox_graph) -> str:
    role = abox_graph.value(HANS_RECORD, OFR.hasRole)
    parent = abox_graph.value(HANS_RECORD, OFR.partOfRecord)
    obs = next(
        o
        for o in abox_graph.subjects(RDF.type, OFR.FieldObservation)
        if abox_graph.value(o, OFR.aboutRecord) == HANS_RECORD
        and abox_graph.value(o, OFR.observedConcept) == VORNAME_CONCEPT
    )
    value = abox_graph.value(obs, OFR.hasValue)
    return (
        f"<{HANS_RECORD}> ofr:partOfRecord <{parent}> ;\n"
        f"    ofr:hasRole <{role}> .\n\n"
        f"[] a ofr:FieldObservation ;\n"
        f"    ofr:aboutRecord <{HANS_RECORD}> ;\n"
        f"    ofr:observedConcept <{VORNAME_CONCEPT}> ;\n"
        f'    ofr:hasValue "{value}" .'
    )


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


def _xmlo_snippet(xmlo_graph, elements) -> str:
    leaf = _find_hans_vorname_xmlo_element(xmlo_graph, elements)
    return (
        "[] a xmlo:Element ;\n"
        '    xmlo:elementName "Vorname" ;\n'
        f'    xmlo:namespaceURI "{xmlo_graph.value(leaf, XMLO.namespaceURI)}" ;\n'
        '    xmlo:textContent "Hans" ;\n'
        f"    xmlo:childPosition {xmlo_graph.value(leaf, XMLO.childPosition)} ."
    )


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
                {"id": "excel", "title": "Excel", "subtitle": "Personen sheet, row 2", "lang": "text", "snippet": _excel_snippet()},
                {"id": "sso", "title": "SSO graph", "subtitle": "extract_raw_cells", "lang": "turtle", "snippet": _sso_snippet(raw)},
                {"id": "abox", "title": "A-box graph", "subtitle": "interpret_master_detail", "lang": "turtle", "snippet": _abox_snippet(abox)},
                {"id": "xmlo", "title": "XMLO graph", "subtitle": "generate_instance", "lang": "turtle", "snippet": _xmlo_snippet(xmlo_graph, elements)},
                {"id": "xml", "title": "Real XML", "subtitle": "serialize_xmlo_to_xml", "lang": "xml", "snippet": _xml_snippet(instance)},
            ],
        }
    finally:
        shutil.rmtree(fixture_dir, ignore_errors=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


if __name__ == "__main__":
    export(os.environ.get("SHOWCASE_OUTPUT", "showcase-pipeline-data.json"))
