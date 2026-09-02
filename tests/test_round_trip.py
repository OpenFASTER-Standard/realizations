"""End-to-end proof: master-detail .xlsx (Erstattungsantraege + Personen,
with real dropdowns) -> filled-in test data -> ofr:partOfRecord/
recordPosition/hasRole A-box graph -> recursively compiled XMLO graph ->
real, namespace-qualified, correctly-nested XML -- confirmed fragment by
fragment against the real KaFE XSD's own declared structure, not just
internal consistency. Full-document schema validity stays out of scope
(most real Erstattungsantrag_CType/StpflNatP_Struct/... fields are
deliberately uncurated -- see the plan's Global Constraints).
"""
import os

import lxml.etree as etree
import xmlschema
from rdflib import Namespace, URIRef

from generator.xlsx_generator import generate_workbook
from generator.xlsx_ingest import extract_raw_cells, interpret_master_detail
from generator.xml_instance_generator import generate_instance, serialize_xmlo_to_xml
from generator.xsd_generator import load_graph

KAFE = "https://openfaster.org/kafe/schema#"
KAFE_NS = Namespace(KAFE)
IO = "https://purl.openfaster.org/io/IO_"
ANTRAEGE_SHEET = f"{KAFE}ErstAntragSheet"
ID_COLUMN = f"{KAFE}ErstAntragIdColumn"
PERSONEN_SHEET = f"{KAFE}PersonenSheet"
PARENT_KEY_COLUMN = f"{KAFE}PersonenParentIdColumn"
ROLE_COLUMN = f"{KAFE}PersonenRoleColumn"
REAL_XSD = os.environ.get(
    "KAFE_STANDARDTYPES_XSD",
    "/work/openfaster-spec/kafe/kafe-standardtypes.xsd",
)
REAL_KAFE_XSD = os.environ.get(
    "KAFE_XSD",
    "/work/openfaster-spec/kafe/kafe.xsd",
)


def test_full_round_trip_with_repeating_erstattungsantrag_and_roles(tmp_path):
    structure = load_graph("modules/kafe.ttl")
    structure.parse("/work/institutional-ontology/institutional-ontology.owl", format="xml")
    layout = load_graph("layouts/kafe-canonical.ttl")

    # 1. graph -> master-detail canonical template, with real dropdowns
    wb = generate_workbook(structure, layout)
    antraege = wb["Erstattungsantraege"]
    antraege.cell(row=2, column=1, value="A1")
    antraege.cell(row=3, column=1, value="A2")

    personen = wb["Personen"]
    personen.cell(row=2, column=1, value="A1")
    personen.cell(row=2, column=2, value="STEUERPFLICHTIGE_PERSON")
    personen.cell(row=2, column=3, value="HERR")
    personen.cell(row=2, column=4, value="Hans")
    personen.cell(row=2, column=5, value="Muster")
    personen.cell(row=3, column=1, value="A1")
    personen.cell(row=3, column=2, value="GESETZLICHE_VERTRETUNG")
    personen.cell(row=3, column=3, value="FRAU")
    personen.cell(row=3, column=4, value="Erika")
    personen.cell(row=3, column=5, value="Vertreter")
    personen.cell(row=4, column=1, value="A2")
    personen.cell(row=4, column=2, value="STEUERPFLICHTIGE_PERSON")
    personen.cell(row=4, column=3, value="HERR")
    personen.cell(row=4, column=4, value="Peter")
    personen.cell(row=4, column=5, value="Steuer")
    personen.cell(row=5, column=2, value="BEVOLLMAECHTIGTE_PERSON")
    personen.cell(row=5, column=3, value="FRAU")
    personen.cell(row=5, column=4, value="Anna")
    personen.cell(row=5, column=5, value="Vollmacht")

    path = os.path.join(tmp_path, "filled.xlsx")
    wb.save(path)

    # 2. ingest into a real ofr:partOfRecord/recordPosition/hasRole graph
    raw = extract_raw_cells(path)
    submission = URIRef("urn:record:submission:1")
    abox = interpret_master_detail(
        raw, layout, ANTRAEGE_SHEET, ID_COLUMN, PERSONEN_SHEET, PARENT_KEY_COLUMN, ROLE_COLUMN, structure, submission
    )

    # 3. compile the whole KAFE_CType tree + facts into an XMLO graph
    xmlo_graph, elements = generate_instance(structure, KAFE_NS.KAFE_CType, abox, submission)

    # 4. serialize to real, namespace-qualified, correctly nested XML
    instance = serialize_xmlo_to_xml(xmlo_graph, elements)

    # 5. confirm top-level order against the real XSD's own KAFE_CType
    real_schema = xmlschema.XMLSchema(REAL_KAFE_XSD)
    real_kafe_names = [e.local_name for e in real_schema.types["KAFE_CType"].content.iter_elements()]
    generated_top_names = [etree.QName(c).localname for c in instance]
    assert generated_top_names == [n for n in real_kafe_names if n in generated_top_names]
    assert generated_top_names == ["BevollmaechtigtePerson", "Antraege"]

    # 6. Antraege contains 2 real Erstattungsantrag elements, position-ordered
    antraege_el = next(c for c in instance if etree.QName(c).localname == "Antraege")
    erst_els = list(antraege_el)
    assert [etree.QName(c).localname for c in erst_els] == ["Erstattungsantrag", "Erstattungsantrag"]
    assert all(etree.QName(c).namespace == "urn:bzst:kafe:ozg:v1" for c in erst_els)

    # 7. First Erstattungsantrag (A1): AllgAngaben -> both SteuerpflichtigePerson
    #    and GesetzlicheVertretung, matching real AllgAngaben_CType order.
    allg1 = erst_els[0][0]
    assert etree.QName(allg1).localname == "AllgAngaben"
    real_allg_names = [e.local_name for e in real_schema.types["AllgAngaben_CType"].content.iter_elements()]
    generated_allg1_names = [etree.QName(c).localname for c in allg1]
    assert generated_allg1_names == [n for n in real_allg_names if n in generated_allg1_names]
    assert generated_allg1_names == ["SteuerpflichtigePerson", "GesetzlicheVertretung"]

    def _nachname(role_wrapper_el, natp_depth):
        node = role_wrapper_el
        for _ in range(natp_depth):
            node = node[0]
        leaf = next(c for c in node if etree.QName(c).localname == "Nachname")
        return leaf.text

    stpfl1 = next(c for c in allg1 if etree.QName(c).localname == "SteuerpflichtigePerson")
    assert _nachname(stpfl1, natp_depth=2) == "Muster"  # SteuerpflichtigePerson -> NatuerlichePerson -> NatP -> leaves
    gv1 = next(c for c in allg1 if etree.QName(c).localname == "GesetzlicheVertretung")
    assert _nachname(gv1, natp_depth=1) == "Vertreter"  # GesetzlicheVertretung -> NatuerlichePerson -> leaves

    # 8. Second Erstattungsantrag (A2): only SteuerpflichtigePerson (no
    #    legal representative for this one).
    allg2 = erst_els[1][0]
    generated_allg2_names = [etree.QName(c).localname for c in allg2]
    assert generated_allg2_names == ["SteuerpflichtigePerson"]
    stpfl2 = allg2[0]
    assert _nachname(stpfl2, natp_depth=2) == "Steuer"

    # 9. Submission-level BevollmaechtigtePerson, sibling of Antraege
    bev_el = next(c for c in instance if etree.QName(c).localname == "BevollmaechtigtePerson")
    assert _nachname(bev_el, natp_depth=1) == "Vollmacht"

    # 10. Real Anrede tokens throughout, not invented ones
    real_anrede_values = set(
        xmlschema.XMLSchema(REAL_XSD).types["Anrede_ENUM"].facets[
            "{http://www.w3.org/2001/XMLSchema}enumeration"
        ].enumeration
    )
    all_anrede = instance.iter("{urn:bzst:kafe:ozg:v1}Anrede")
    assert all(el.text in real_anrede_values for el in all_anrede)
