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
