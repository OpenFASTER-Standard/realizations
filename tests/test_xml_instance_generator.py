from lxml import etree
from rdflib import RDF, BNode, Graph, Literal, Namespace, URIRef

from generator.xml_instance_generator import XMLO, generate_instance, serialize_xmlo_to_xml
from generator.xsd_generator import load_graph

KAFE = "https://openfaster.org/kafe/schema#"
IO = "https://purl.openfaster.org/io/IO_"
OFR = Namespace("https://openfaster.org/realizations/schema#")


def _abox_graph():
    g = Graph()
    record = URIRef("urn:record:2")
    obs1, obs2, obs3 = BNode(), BNode(), BNode()
    for obs, concept, value in [
        (obs1, URIRef(f"{IO}0000003"), URIRef(f"{IO}0000005")),  # Anrede -> Mr.
        (obs2, URIRef(f"{IO}0000001"), Literal("Hans")),
        (obs3, URIRef(f"{IO}0000002"), Literal("Muster")),
    ]:
        g.add((obs, RDF.type, OFR.FieldObservation))
        g.add((obs, OFR.aboutRecord, record))
        g.add((obs, OFR.observedConcept, concept))
        g.add((obs, OFR.hasValue, value))
    return g, record


def test_generates_real_populated_natp_struct_elements():
    structure = load_graph("modules/kafe.ttl")
    abox, record = _abox_graph()

    xmlo_graph, elements = generate_instance(
        structure, URIRef(f"{KAFE}NatP_Struct"), abox, record
    )

    ordered = sorted(elements, key=lambda e: int(xmlo_graph.value(e, XMLO.childPosition)))
    names = [str(xmlo_graph.value(e, XMLO.elementName)) for e in ordered]
    assert names == ["Anrede", "Vorname", "Nachname"]

    texts = [str(xmlo_graph.value(e, XMLO.textContent)) for e in ordered]
    assert texts == ["HERR", "Hans", "Muster"]

    # Real namespace-qualification, the concrete gap this plan fixes
    for e in ordered:
        assert str(xmlo_graph.value(e, XMLO.namespaceURI)) == "urn:bzst:kafe:ozg:v1"


def test_serializes_xmlo_graph_to_real_namespace_qualified_xml():
    structure = load_graph("modules/kafe.ttl")
    abox, record = _abox_graph()
    xmlo_graph, elements = generate_instance(structure, URIRef(f"{KAFE}NatP_Struct"), abox, record)

    root = serialize_xmlo_to_xml(xmlo_graph, elements)
    children = list(root)

    assert [etree.QName(c).localname for c in children] == ["Anrede", "Vorname", "Nachname"]
    assert all(etree.QName(c).namespace == "urn:bzst:kafe:ozg:v1" for c in children)
    assert [c.text for c in children] == ["HERR", "Hans", "Muster"]
