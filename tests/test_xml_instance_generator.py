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


def test_recurses_into_a_nested_complex_type():
    structure = load_graph("modules/kafe.ttl")
    g = Graph()
    person_record = URIRef("urn:record:legalrep:1")
    obs1, obs2, obs3 = BNode(), BNode(), BNode()
    for obs, concept, value in [
        (obs1, URIRef(f"{IO}0000003"), URIRef(f"{IO}0000004")),  # Anrede -> Ms.
        (obs2, URIRef(f"{IO}0000001"), Literal("Erika")),
        (obs3, URIRef(f"{IO}0000002"), Literal("Vertreter")),
    ]:
        g.add((obs, RDF.type, OFR.FieldObservation))
        g.add((obs, OFR.aboutRecord, person_record))
        g.add((obs, OFR.observedConcept, concept))
        g.add((obs, OFR.hasValue, value))

    KAFE_NS = Namespace(KAFE)
    xmlo_graph, elements = generate_instance(
        structure, KAFE_NS.GesetzlicheVertretung_Struct, g, person_record
    )

    assert len(elements) == 1
    wrapper = elements[0]
    assert str(xmlo_graph.value(wrapper, XMLO.elementName)) == "NatuerlichePerson"

    children = sorted(
        xmlo_graph.objects(wrapper, XMLO.hasChildElement),
        key=lambda e: int(xmlo_graph.value(e, XMLO.childPosition)),
    )
    names = [str(xmlo_graph.value(c, XMLO.elementName)) for c in children]
    texts = [str(xmlo_graph.value(c, XMLO.textContent)) for c in children]
    assert names == ["Anrede", "Vorname", "Nachname"]
    assert texts == ["FRAU", "Erika", "Vertreter"]


TAXPAYER_ROLE = URIRef(f"{IO}0000008")
LEGAL_REP_ROLE = URIRef(f"{IO}0000009")


def _person_facts(g, record, anrede_io, given_name, family_name):
    obs1, obs2, obs3 = BNode(), BNode(), BNode()
    for obs, concept, value in [
        (obs1, URIRef(f"{IO}0000003"), URIRef(anrede_io)),
        (obs2, URIRef(f"{IO}0000001"), Literal(given_name)),
        (obs3, URIRef(f"{IO}0000002"), Literal(family_name)),
    ]:
        g.add((obs, RDF.type, OFR.FieldObservation))
        g.add((obs, OFR.aboutRecord, record))
        g.add((obs, OFR.observedConcept, concept))
        g.add((obs, OFR.hasValue, value))


def test_role_scoped_element_resolves_via_hasrole_and_skips_when_absent():
    structure = load_graph("modules/kafe.ttl")
    antrag_record = URIRef("urn:record:antrag:1")
    taxpayer = URIRef("urn:record:person:1")
    g = Graph()
    g.add((taxpayer, OFR.partOfRecord, antrag_record))
    g.add((taxpayer, OFR.hasRole, TAXPAYER_ROLE))
    _person_facts(g, taxpayer, f"{IO}0000005", "Hans", "Muster")  # Mr.

    KAFE_NS = Namespace(KAFE)
    xmlo_graph, elements = generate_instance(structure, KAFE_NS.AllgAngaben_CType, g, antrag_record)

    # SteuerpflichtigePerson present (role matched); GesetzlicheVertretung
    # absent (no legal-representative-role sub-entity for this record) --
    # only one top-level element, not two.
    assert len(elements) == 1
    assert str(xmlo_graph.value(elements[0], XMLO.elementName)) == "SteuerpflichtigePerson"


def test_role_scoped_element_present_when_both_roles_exist():
    structure = load_graph("modules/kafe.ttl")
    antrag_record = URIRef("urn:record:antrag:1")
    taxpayer = URIRef("urn:record:person:1")
    legal_rep = URIRef("urn:record:person:2")
    g = Graph()
    g.add((taxpayer, OFR.partOfRecord, antrag_record))
    g.add((taxpayer, OFR.hasRole, TAXPAYER_ROLE))
    _person_facts(g, taxpayer, f"{IO}0000005", "Hans", "Muster")
    g.add((legal_rep, OFR.partOfRecord, antrag_record))
    g.add((legal_rep, OFR.hasRole, LEGAL_REP_ROLE))
    _person_facts(g, legal_rep, f"{IO}0000004", "Erika", "Vertreter")  # Ms.

    KAFE_NS = Namespace(KAFE)
    xmlo_graph, elements = generate_instance(structure, KAFE_NS.AllgAngaben_CType, g, antrag_record)

    names = [str(xmlo_graph.value(e, XMLO.elementName)) for e in elements]
    assert names == ["SteuerpflichtigePerson", "GesetzlicheVertretung"]  # real particle order


def test_repeating_particle_expands_one_element_per_position_ordered_subentity():
    structure = load_graph("modules/kafe.ttl")
    submission = URIRef("urn:record:submission:1")
    antrag1 = URIRef("urn:record:antrag:1")
    antrag2 = URIRef("urn:record:antrag:2")
    taxpayer1 = URIRef("urn:record:person:1")
    taxpayer2 = URIRef("urn:record:person:2")

    g = Graph()
    g.add((antrag1, OFR.partOfRecord, submission))
    g.add((antrag1, OFR.recordPosition, Literal(1)))
    g.add((antrag2, OFR.partOfRecord, submission))
    g.add((antrag2, OFR.recordPosition, Literal(2)))
    g.add((taxpayer1, OFR.partOfRecord, antrag1))
    g.add((taxpayer1, OFR.hasRole, TAXPAYER_ROLE))
    _person_facts(g, taxpayer1, f"{IO}0000005", "Hans", "Muster")
    g.add((taxpayer2, OFR.partOfRecord, antrag2))
    g.add((taxpayer2, OFR.hasRole, TAXPAYER_ROLE))
    _person_facts(g, taxpayer2, f"{IO}0000004", "Erika", "Zweitantrag")

    KAFE_NS = Namespace(KAFE)
    xmlo_graph, elements = generate_instance(structure, KAFE_NS.Antraege_CType, g, submission)

    assert len(elements) == 2
    assert all(str(xmlo_graph.value(e, XMLO.elementName)) == "Erstattungsantrag" for e in elements)
    ordered = sorted(elements, key=lambda e: int(xmlo_graph.value(e, XMLO.childPosition)))

    # Walk down each Erstattungsantrag -> AllgAngaben -> SteuerpflichtigePerson
    # -> NatuerlichePerson -> NatP -> Nachname to confirm the RIGHT taxpayer's
    # data landed under the RIGHT Erstattungsantrag, in position order.
    def _nachname(erst_element):
        allg = xmlo_graph.value(erst_element, XMLO.hasChildElement)
        stpfl = xmlo_graph.value(allg, XMLO.hasChildElement)
        natp_wrap = xmlo_graph.value(stpfl, XMLO.hasChildElement)
        natp = xmlo_graph.value(natp_wrap, XMLO.hasChildElement)
        children = list(xmlo_graph.objects(natp, XMLO.hasChildElement))
        nachname_el = next(c for c in children if str(xmlo_graph.value(c, XMLO.elementName)) == "Nachname")
        return str(xmlo_graph.value(nachname_el, XMLO.textContent))

    assert _nachname(ordered[0]) == "Muster"
    assert _nachname(ordered[1]) == "Zweitantrag"


def test_serializes_xmlo_graph_to_real_namespace_qualified_xml():
    structure = load_graph("modules/kafe.ttl")
    abox, record = _abox_graph()
    xmlo_graph, elements = generate_instance(structure, URIRef(f"{KAFE}NatP_Struct"), abox, record)

    root = serialize_xmlo_to_xml(xmlo_graph, elements)
    children = list(root)

    assert [etree.QName(c).localname for c in children] == ["Anrede", "Vorname", "Nachname"]
    assert all(etree.QName(c).namespace == "urn:bzst:kafe:ozg:v1" for c in children)
    assert [c.text for c in children] == ["HERR", "Hans", "Muster"]
