from lxml import etree
from rdflib import URIRef

from generator.xsd_generator import generate_complex_type, load_graph

KAFE = "https://openfaster.org/kafe/schema#"


def test_generates_natp_struct_sequence_in_real_document_order():
    graph = load_graph("modules/kafe.ttl")
    complex_type = generate_complex_type(graph, URIRef(f"{KAFE}NatP_Struct"))

    sequence = complex_type[0]
    assert etree.QName(sequence).localname == "sequence"

    elements = list(sequence)
    assert [e.get("name") for e in elements] == [
        "Anrede", "Titel", "Vorname", "Nachname",
    ]
    assert elements[1].get("minOccurs") == "0"       # Titel is optional
    assert elements[0].get("type") == "kafe:Anrede_ENUM"   # curated in SSO Task 9
    assert elements[1].get("type") is None            # Titel still uncurated
    assert elements[2].get("type") == "kafe:Vorname_Type"
    assert elements[3].get("type") == "kafe:Nachname_Type"
