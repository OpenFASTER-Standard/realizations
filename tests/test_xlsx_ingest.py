import os

from generator.xlsx_generator import generate_workbook
from generator.xlsx_ingest import extract_raw_cells, interpret_positional
from generator.xsd_generator import load_graph
from rdflib import RDF, Namespace, URIRef

SSO = Namespace("https://purl.openfaster.org/sso/")
OFR = Namespace("https://openfaster.org/realizations/schema#")


def _load_structure_and_layout():
    structure = load_graph("modules/kafe.ttl")
    structure.parse("/work/institutional-ontology/institutional-ontology.owl", format="xml")
    layout = load_graph("layouts/kafe-canonical.ttl")
    return structure, layout


def test_extracts_every_nonempty_cell_regardless_of_shape(tmp_path):
    structure, layout = _load_structure_and_layout()
    wb = generate_workbook(structure, layout, "https://openfaster.org/kafe/schema#CanonicalSheet")
    ws = wb["NatuerlichePersonen"]
    ws.cell(row=2, column=1, value="HERR")
    ws.cell(row=2, column=2, value="Hans")
    ws.cell(row=2, column=3, value="Muster")

    path = os.path.join(tmp_path, "filled.xlsx")
    wb.save(path)

    graph = extract_raw_cells(path)
    values = {
        (int(graph.value(c, SSO.rowIndex)), int(graph.value(c, SSO.columnIndex))): str(graph.value(c, SSO.literalValue))
        for c in graph.subjects(None, None)
        if (c, SSO.rowIndex, None) in graph
    }
    assert values[(1, 1)] == "Form of address"
    assert values[(2, 1)] == "HERR"
    assert values[(2, 2)] == "Hans"
    assert values[(2, 3)] == "Muster"


def test_interprets_positional_layout_into_concept_linked_values(tmp_path):
    structure, layout = _load_structure_and_layout()
    wb = generate_workbook(structure, layout, "https://openfaster.org/kafe/schema#CanonicalSheet")
    ws = wb["NatuerlichePersonen"]
    ws.cell(row=2, column=1, value="HERR")
    ws.cell(row=2, column=2, value="Hans")
    ws.cell(row=2, column=3, value="Muster")
    path = os.path.join(tmp_path, "filled.xlsx")
    wb.save(path)

    raw = extract_raw_cells(path)
    obs_graph = interpret_positional(
        raw, layout, "https://openfaster.org/kafe/schema#CanonicalSheet", structure
    )

    IO = "https://purl.openfaster.org/io/IO_"
    record = URIRef("urn:record:2")
    values = {
        str(obs_graph.value(obs, OFR.observedConcept)): obs_graph.value(obs, OFR.hasValue)
        for obs in obs_graph.subjects(RDF.type, OFR.FieldObservation)
        if obs_graph.value(obs, OFR.aboutRecord) == record
    }
    assert values[f"{IO}0000003"] == URIRef(f"{IO}0000005")  # HERR resolved to the Mr. individual
    assert str(values[f"{IO}0000001"]) == "Hans"
    assert str(values[f"{IO}0000002"]) == "Muster"
