from rdflib import Graph

from generator.xlsx_generator import generate_workbook

KAFE = "https://openfaster.org/kafe/schema#"


def _load(*paths):
    g = Graph()
    for p in paths:
        fmt = "xml" if p.endswith(".owl") else "turtle"
        g.parse(p, format=fmt)
    return g


def test_generates_both_master_detail_sheets_with_headers_and_dropdowns():
    structure = _load("modules/kafe.ttl", "/work/institutional-ontology/institutional-ontology.owl")
    layout = _load("layouts/kafe-canonical.ttl")

    wb = generate_workbook(structure, layout)

    assert wb.sheetnames == ["Erstattungsantraege", "Personen"]

    antraege = wb["Erstattungsantraege"]
    assert antraege.cell(row=1, column=1).value == "Antrag-ID"

    personen = wb["Personen"]
    assert [personen.cell(row=1, column=c).value for c in (1, 2, 3, 4, 5)] == [
        "Zugehörige Antrag-ID", "Person role", "Form of address", "All given names", "Last name",
    ]

    dv_by_range = {str(dv.sqref): dv for dv in personen.data_validations.dataValidation}
    role_dv = next(dv for r, dv in dv_by_range.items() if "B2" in r)
    assert role_dv.formula1 == '"BEVOLLMAECHTIGTE_PERSON,GESETZLICHE_VERTRETUNG,STEUERPFLICHTIGE_PERSON"'
    anrede_dv = next(dv for r, dv in dv_by_range.items() if "C2" in r)
    assert anrede_dv.formula1 == '"FRAU,HERR,KEINE_ANREDE"'
