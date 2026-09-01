from lxml import etree
from rdflib import URIRef

from generator.xml_instance_generator import generate_instance
from generator.xsd_generator import load_graph

KAFE = "https://openfaster.org/kafe/schema#"
IO = "https://purl.openfaster.org/io/IO_"


def test_generates_real_populated_natp_struct_element():
    graph = load_graph("modules/kafe.ttl")
    values_by_concept = {
        f"{IO}0000003": "HERR",
        f"{IO}0000001": "Hans",
        f"{IO}0000002": "Muster",
    }

    instance = generate_instance(graph, URIRef(f"{KAFE}NatP_Struct"), values_by_concept)

    children = list(instance)
    assert [etree.QName(c).localname for c in children] == [
        "Anrede", "Vorname", "Nachname",
    ]
    assert children[0].text == "HERR"
    assert children[1].text == "Hans"
    assert children[2].text == "Muster"
