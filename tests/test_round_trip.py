"""End-to-end proof: graph -> canonical .xlsx (with a real dropdown) ->
filled-in test data -> ingested back into a real ofr:FieldObservation
graph -> compiled into an XMLO graph -> real, namespace-qualified XML --
confirmed against the real KaFE XSD itself, not just internal
consistency.
"""
import os

import lxml.etree as etree
import xmlschema
from rdflib import URIRef

from generator.xlsx_generator import generate_workbook
from generator.xlsx_ingest import extract_raw_cells, interpret_positional
from generator.xml_instance_generator import generate_instance, serialize_xmlo_to_xml
from generator.xsd_generator import load_graph

KAFE = "https://openfaster.org/kafe/schema#"
IO = "https://purl.openfaster.org/io/IO_"
SHEET = f"{KAFE}CanonicalSheet"
REAL_XSD = os.environ.get(
    "KAFE_STANDARDTYPES_XSD",
    "/work/openfaster-spec/kafe/kafe-standardtypes.xsd",
)


def test_full_round_trip_matches_the_real_xsd(tmp_path):
    structure = load_graph("modules/kafe.ttl")
    structure.parse("/work/institutional-ontology/institutional-ontology.owl", format="xml")
    layout = load_graph("layouts/kafe-canonical.ttl")

    # 1. graph -> canonical template, with a real Anrede dropdown
    wb = generate_workbook(structure, layout, SHEET)
    ws = wb["NatuerlichePersonen"]
    dv = ws.data_validations.dataValidation[0]
    real_schema = xmlschema.XMLSchema(REAL_XSD)
    real_anrede_values = sorted(
        real_schema.types["Anrede_ENUM"].facets[
            "{http://www.w3.org/2001/XMLSchema}enumeration"
        ].enumeration
    )
    assert dv.formula1 == f'"{",".join(real_anrede_values)}"'

    # 2. fill in test values programmatically, not by hand
    ws.cell(row=2, column=1, value="HERR")
    ws.cell(row=2, column=2, value="Hans")
    ws.cell(row=2, column=3, value="Muster")
    path = os.path.join(tmp_path, "filled.xlsx")
    wb.save(path)

    # 3. ingest into a real ofr:FieldObservation graph, not a dict
    raw = extract_raw_cells(path)
    abox = interpret_positional(raw, layout, SHEET, structure)
    record = URIRef("urn:record:2")

    # 4. compile structure + facts into an XMLO graph
    xmlo_graph, elements = generate_instance(structure, URIRef(f"{KAFE}NatP_Struct"), abox, record)

    # 5. serialize to real, namespace-qualified XML
    instance = serialize_xmlo_to_xml(xmlo_graph, elements)

    # 6. confirm against the real XSD: element order, names, real enum tokens, namespace
    real_type = real_schema.types["NatP_Struct"]
    real_names_in_order = [e.local_name for e in real_type.content.iter_elements()]
    generated_names = [etree.QName(c).localname for c in instance]
    expected = [n for n in real_names_in_order if n in generated_names]
    assert generated_names == expected

    assert all(etree.QName(c).namespace == "urn:bzst:kafe:ozg:v1" for c in instance)

    values_by_tag = {etree.QName(c).localname: c.text for c in instance}
    assert values_by_tag["Anrede"] in real_anrede_values
    assert values_by_tag["Vorname"] == "Hans"
    assert values_by_tag["Nachname"] == "Muster"
