import os

from generator.xlsx_generator import generate_workbook
from generator.xlsx_ingest import extract_raw_cells
from generator.xsd_generator import load_graph
from rdflib import Namespace

SSO = Namespace("https://purl.openfaster.org/sso/")


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
