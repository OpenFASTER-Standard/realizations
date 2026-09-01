"""Confirms the generator's output for curated fields matches the real,
hand-written KaFE XSD -- the concrete, incremental proof of graph/XSD
parity described in docs/superpowers/specs/2026-09-01-xsd-ontology-design.md.
"""
import os

import xmlschema
from rdflib import URIRef

from generator.xsd_generator import generate_complex_type, load_graph

KAFE = "https://openfaster.org/kafe/schema#"
REAL_XSD = os.environ.get(
    "KAFE_STANDARDTYPES_XSD",
    "/work/openfaster-spec/kafe/kafe-standardtypes.xsd",
)


def _real_natp_struct_children():
    schema = xmlschema.XMLSchema(REAL_XSD)
    real_type = schema.types["NatP_Struct"]
    return list(real_type.content.iter_elements())


def test_curated_fields_match_the_real_xsd_type_and_relative_order():
    graph = load_graph("modules/kafe.ttl")
    generated = generate_complex_type(graph, URIRef(f"{KAFE}NatP_Struct"))
    generated_by_name = {e.get("name"): e for e in generated[0]}

    real_children = _real_natp_struct_children()
    real_by_name = {c.local_name: c for c in real_children}

    for field_name, real_type_name in [
        ("Vorname", "Vorname_Type"),
        ("Nachname", "Nachname_Type"),
    ]:
        assert real_by_name[field_name].type.local_name == real_type_name
        assert generated_by_name[field_name].get("type") == f"kafe:{real_type_name}"

    # Real document order must be preserved for the curated fields, even
    # though positions 1-2 (Anrede, Titel) aren't curated yet.
    real_order = [c.local_name for c in real_children]
    generated_order = list(generated_by_name)
    curated_in_real_order = [n for n in real_order if n in generated_order]
    assert curated_in_real_order == generated_order
