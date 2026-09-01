"""Raw .xlsx -> SSO-shaped RDF extraction. Mechanical and structure-agnostic:
every non-empty cell across every sheet becomes a triple set, with zero
interpretation of what any cell means. Works on any .xlsx regardless of
shape -- this is the step that makes "a sheet has no assumed structure"
concrete.
"""
from __future__ import annotations

from openpyxl import load_workbook
from rdflib import Graph, Literal, Namespace, URIRef

SSO = Namespace("https://purl.openfaster.org/sso/")
OFR = Namespace("https://openfaster.org/realizations/schema#")


def extract_raw_cells(path: str) -> Graph:
    graph = Graph()
    graph.bind("sso", SSO)
    wb = load_workbook(path, data_only=True)

    workbook_node = URIRef(f"urn:sso:workbook:{path}")

    for position, sheet_name in enumerate(wb.sheetnames, start=1):
        ws = wb[sheet_name]
        sheet_node = URIRef(f"{workbook_node}/sheet/{sheet_name}")
        graph.add((workbook_node, SSO.hasSheet, sheet_node))
        graph.add((sheet_node, SSO.sheetName, Literal(sheet_name)))
        graph.add((sheet_node, SSO.sheetPosition, Literal(position)))

        for row in ws.iter_rows():
            for cell in row:
                if cell.value is None:
                    continue
                cell_node = URIRef(f"{sheet_node}/cell/{cell.row}/{cell.column}")
                graph.add((sheet_node, SSO.hasCell, cell_node))
                graph.add((cell_node, SSO.rowIndex, Literal(cell.row)))
                graph.add((cell_node, SSO.columnIndex, Literal(cell.column)))
                graph.add((cell_node, SSO.literalValue, Literal(str(cell.value))))
                graph.add((cell_node, SSO.valueType, SSO.stringValue))

    return graph


def interpret_positional(raw_graph: Graph, layout_graph: Graph, sheet_iri: str) -> dict[str, list[dict]]:
    """Walk a raw cell graph via a positional layout definition, producing
    real concept-linked values. The sheet name in the layout must match the
    sheet name actually present in the raw (ingested) workbook -- this MVP
    doesn't attempt cross-sheet-name matching.
    """
    sheet_name = str(layout_graph.value(URIRef(sheet_iri), SSO.sheetName))
    raw_sheet = next(
        s for s in raw_graph.subjects(SSO.sheetName, Literal(sheet_name))
    )

    columns = list(layout_graph.subjects(SSO.sheet, URIRef(sheet_iri)))
    results: dict[str, list[dict]] = {}

    for column in columns:
        concept = str(layout_graph.value(column, OFR.realizesConcept))
        col_index = int(layout_graph.value(column, SSO.columnIndex))
        data_start = int(layout_graph.value(column, SSO.dataStartRow))

        rows = []
        for cell in raw_graph.objects(raw_sheet, SSO.hasCell):
            row_idx = int(raw_graph.value(cell, SSO.rowIndex))
            cell_col = int(raw_graph.value(cell, SSO.columnIndex))
            if cell_col == col_index and row_idx >= data_start:
                rows.append({
                    "row": row_idx,
                    "value": str(raw_graph.value(cell, SSO.literalValue)),
                })
        rows.sort(key=lambda r: r["row"])
        results[concept] = rows

    return results
