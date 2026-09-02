"""A-box graph -> XMLO graph. Sibling to xsd_generator.py's schema
generator: same tree-walk (ComplexTypeDefinition -> Sequence -> ordered
Particles), but compiles kafe.ttl's structure + a real record's
ofr:FieldObservation facts into an XMLO-shaped graph representing one
concrete instance, instead of emitting lxml elements directly. Actual XML
text comes from serialize_xmlo_to_xml, a separate, purely mechanical step.
Recurses into nested ComplexTypeDefinition terms so real containment
(Erstattungsantrag -> AllgAngaben -> SteuerpflichtigePerson -> ... ->
NatP_Struct) round-trips faithfully, not just the single flat type this
function originally supported.
"""
from __future__ import annotations

from lxml import etree
from rdflib import RDF, BNode, Graph, Literal, Namespace, URIRef

from generator.xsd_generator import XSDO, _ordered_particles

OFR = Namespace("https://openfaster.org/realizations/schema#")
XMLO = Namespace("https://purl.openfaster.org/xmlo/")


def _values_for_record(abox_graph: Graph, record: URIRef) -> dict[str, object]:
    values = {}
    for obs in abox_graph.subjects(RDF.type, OFR.FieldObservation):
        if abox_graph.value(obs, OFR.aboutRecord) != record:
            continue
        concept = abox_graph.value(obs, OFR.observedConcept)
        values[str(concept)] = abox_graph.value(obs, OFR.hasValue)
    return values


def _resolve_enumeration_token(structure_graph: Graph, xsd_type, individual) -> str:
    """Inverse of xlsx_ingest._resolve_enumeration_value: given the IO:
    individual an enumerated field's value resolved to, find the
    EnumerationValue whose realizesConcept matches it and return its raw
    XSD token.
    """
    for enum_value in structure_graph.objects(xsd_type, XSDO.hasEnumerationValue):
        if structure_graph.value(enum_value, OFR.realizesConcept) == individual:
            return str(structure_graph.value(enum_value, XSDO.literalValue))
    raise ValueError(f"No EnumerationValue resolves to {individual}")


def _is_complex(structure_graph: Graph, xsd_type) -> bool:
    return xsd_type is not None and (xsd_type, RDF.type, XSDO.ComplexTypeDefinition) in structure_graph


def _build_element(xmlo_graph: Graph, structure_graph: Graph, abox_graph: Graph, term, xsd_type, namespace, record):
    """Emit one XMLO Element for `term`, scoped to `record`. Returns None if
    there's nothing to say (an uncurated leaf, or a complex wrapper whose
    every child is itself empty) -- matches minOccurs=0 skip semantics.
    """
    el = BNode()
    xmlo_graph.add((el, RDF.type, XMLO.Element))
    xmlo_graph.add((el, XMLO.elementName, structure_graph.value(term, XSDO.name)))
    if namespace is not None:
        xmlo_graph.add((el, XMLO.namespaceURI, namespace))

    if _is_complex(structure_graph, xsd_type):
        content_model = structure_graph.value(xsd_type, XSDO.contentModel)
        children = []
        for child_particle in _ordered_particles(structure_graph, content_model):
            children.extend(
                _generate_particle(xmlo_graph, structure_graph, abox_graph, child_particle, namespace, record)
            )
        if not children:
            return None
        for position, child in enumerate(children, start=1):
            xmlo_graph.add((child, XMLO.childPosition, Literal(position)))
            xmlo_graph.add((el, XMLO.hasChildElement, child))
        return el

    concept = structure_graph.value(term, OFR.realizesConcept)
    values = _values_for_record(abox_graph, record)
    if concept is None or str(concept) not in values:
        return None
    value = values[str(concept)]
    text = _resolve_enumeration_token(structure_graph, xsd_type, value) if isinstance(value, URIRef) else str(value)
    xmlo_graph.add((el, XMLO.textContent, Literal(text)))
    return el


def _sub_entities_for_role(abox_graph: Graph, parent_record: URIRef, role) -> list:
    return [
        entity
        for entity in abox_graph.subjects(OFR.hasRole, role)
        if abox_graph.value(entity, OFR.partOfRecord) == parent_record
    ]


def _sub_entities_by_position(abox_graph: Graph, parent_record: URIRef) -> list:
    positioned = [
        (int(abox_graph.value(entity, OFR.recordPosition)), entity)
        for entity in abox_graph.subjects(OFR.partOfRecord, parent_record)
        if abox_graph.value(entity, OFR.recordPosition) is not None
    ]
    return [entity for _, entity in sorted(positioned, key=lambda pair: pair[0])]


def _generate_particle(xmlo_graph: Graph, structure_graph: Graph, abox_graph: Graph, particle, namespace, record) -> list:
    """Returns the list of XMLO Element nodes this particle resolves to for
    `record`: 0 (not curated / role absent), 1 (ordinary or role-scoped),
    or many (a repeating particle, one per position-ordered sub-entity --
    this plan's real case is kafe:Antraege_Erstattungsantrag,
    maxOccurs=500). Repeating + role-scoped combined isn't needed by any
    real KaFE particle modeled in this plan and isn't supported.
    """
    term = structure_graph.value(particle, XSDO["term"])
    if (term, RDF.type, XSDO.ElementDeclaration) not in structure_graph:
        raise NotImplementedError(f"Only ElementDeclaration particle terms are supported: {term}")

    max_occurs_raw = structure_graph.value(particle, XSDO.maxOccurs)
    max_occurs = int(max_occurs_raw) if max_occurs_raw is not None else 1
    xsd_type = structure_graph.value(term, XSDO["type"])
    role = structure_graph.value(term, OFR.impliesRole)

    if max_occurs > 1:
        sub_records = _sub_entities_by_position(abox_graph, record)
        elements = []
        for sub_record in sub_records:
            el = _build_element(xmlo_graph, structure_graph, abox_graph, term, xsd_type, namespace, sub_record)
            if el is not None:
                elements.append(el)
        return elements

    if role is not None:
        matches = _sub_entities_for_role(abox_graph, record, role)
        if not matches:
            return []
        el = _build_element(xmlo_graph, structure_graph, abox_graph, term, xsd_type, namespace, matches[0])
        return [el] if el is not None else []

    el = _build_element(xmlo_graph, structure_graph, abox_graph, term, xsd_type, namespace, record)
    return [el] if el is not None else []


def generate_instance(
    structure_graph: Graph, complex_type: URIRef, abox_graph: Graph, record: URIRef
) -> tuple[Graph, list]:
    """Compile kafe.ttl's XSDO structure + one real record's
    ofr:FieldObservation facts into an XMLO-shaped graph. Returns
    (xmlo_graph, ordered_element_nodes) -- the ordered top-level Elements
    this complex_type's content resolves to for this record. Not wrapped
    in a Document/rootElement -- same fragment-level scope as
    xsd_generator.generate_complex_type.
    """
    xmlo_graph = Graph()
    xmlo_graph.bind("xmlo", XMLO)

    content_model = structure_graph.value(complex_type, XSDO.contentModel)
    namespace = structure_graph.value(complex_type, XSDO.targetNamespace)

    elements = []
    for particle in _ordered_particles(structure_graph, content_model):
        elements.extend(_generate_particle(xmlo_graph, structure_graph, abox_graph, particle, namespace, record))

    for position, el in enumerate(elements, start=1):
        xmlo_graph.add((el, XMLO.childPosition, Literal(position)))

    return xmlo_graph, elements


def _ordered_by_position(xmlo_graph: Graph, elements) -> list:
    return sorted(elements, key=lambda e: int(xmlo_graph.value(e, XMLO.childPosition)))


def _serialize_element(xmlo_graph: Graph, el) -> etree._Element:
    name = str(xmlo_graph.value(el, XMLO.elementName))
    namespace = xmlo_graph.value(el, XMLO.namespaceURI)
    tag = f"{{{namespace}}}{name}" if namespace is not None else name
    node = etree.Element(tag)

    children = list(xmlo_graph.objects(el, XMLO.hasChildElement))
    if children:
        for child in _ordered_by_position(xmlo_graph, children):
            node.append(_serialize_element(xmlo_graph, child))
    else:
        text = xmlo_graph.value(el, XMLO.textContent)
        if text is not None:
            node.text = str(text)
    return node


def serialize_xmlo_to_xml(xmlo_graph: Graph, elements: list) -> etree._Element:
    """Purely mechanical: walk an already-ordered/named/valued/nested XMLO
    graph and emit real XML, recursing through xmlo:hasChildElement. No
    schema knowledge needed anymore -- symmetric to how extract_raw_cells
    reads raw bytes into a graph on the input side.
    """
    root = etree.Element("instance")
    for el in _ordered_by_position(xmlo_graph, elements):
        root.append(_serialize_element(xmlo_graph, el))
    return root
