from rdflib import Graph

from generator.xlsx_generator import generate_workbook

KAFE = "https://openfaster.org/kafe/schema#"


def _load(*paths):
    g = Graph()
    for p in paths:
        fmt = "xml" if p.endswith(".owl") else "turtle"
        g.parse(p, format=fmt)
    return g


def test_generates_canonical_template_with_headers_and_anrede_dropdown():
    # Headers come from IO: concept labels, so institutional-ontology's own
    # data has to be loaded alongside kafe.ttl -- structure/layout alone
    # don't carry rdfs:label for the concepts they merely reference.
    structure = _load("modules/kafe.ttl", "/work/institutional-ontology/institutional-ontology.owl")
    layout = _load("layouts/kafe-canonical.ttl")

    wb = generate_workbook(structure, layout, f"{KAFE}CanonicalSheet")
    sheet = wb["NatuerlichePersonen"]

    assert [sheet.cell(row=1, column=c).value for c in (1, 2, 3)] == [
        "Form of address", "All given names", "Last name",
    ]

    dv_ranges = [str(dv.sqref) for dv in sheet.data_validations.dataValidation]
    assert any("A2" in r for r in dv_ranges)  # Anrede column has a dropdown
    anrede_dv = sheet.data_validations.dataValidation[0]
    assert anrede_dv.formula1 == '"FRAU,HERR,KEINE_ANREDE"'
