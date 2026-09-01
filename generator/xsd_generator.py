"""Graph -> XSD generator. Structurally the inverse of
openfaster-spec/engine/xsd_model.py: walks an XSDO-shaped RDF graph
instead of parsing an .xsd file, and emits XSD elements instead of
extracting field facts from real XSD text.
"""
from __future__ import annotations

from lxml import etree
from rdflib import RDF, Graph, Namespace, URIRef

XSDO = Namespace("https://purl.openfaster.org/xsdo/")
XS_NS = "http://www.w3.org/2001/XMLSchema"

_MODEL_GROUP_TAG = {
    XSDO.Sequence: "sequence",
    XSDO.Choice: "choice",
    XSDO.All: "all",
}


def load_graph(*paths: str) -> Graph:
    graph = Graph()
    for path in paths:
        graph.parse(path, format="turtle")
    return graph


def _ordered_particles(graph: Graph, model_group: URIRef) -> list[URIRef]:
    particles = list(graph.objects(model_group, XSDO.hasParticle))
    return sorted(
        particles,
        key=lambda p: int(graph.value(p, XSDO.particlePosition)),
    )


def _emit_particle(graph: Graph, parent: etree._Element, particle: URIRef) -> None:
    # XSDO["term"], not XSDO.term: rdflib.Namespace has a real .term() method
    # (used to build a URIRef from a name), which attribute access resolves
    # to instead of falling through to Namespace's URIRef-construction
    # __getattr__ -- item access isn't shadowed the same way.
    term = graph.value(particle, XSDO["term"])
    if (term, RDF.type, XSDO.ElementDeclaration) not in graph:
        raise NotImplementedError(
            f"Only ElementDeclaration particle terms are supported so far: {term}"
        )

    element = etree.SubElement(parent, f"{{{XS_NS}}}element")
    element.set("name", str(graph.value(term, XSDO.name)))

    xsd_type = graph.value(term, XSDO.type)
    if xsd_type is not None:
        element.set("type", graph.qname(xsd_type))

    min_occurs = graph.value(particle, XSDO.minOccurs)
    if min_occurs is not None and int(min_occurs) != 1:
        element.set("minOccurs", str(min_occurs))

    unbounded = graph.value(particle, XSDO.maxOccursUnbounded)
    if unbounded is not None and str(unbounded).lower() == "true":
        element.set("maxOccurs", "unbounded")
    else:
        max_occurs = graph.value(particle, XSDO.maxOccurs)
        if max_occurs is not None and int(max_occurs) != 1:
            element.set("maxOccurs", str(max_occurs))


def _emit_model_group(
    graph: Graph, parent: etree._Element, model_group: URIRef
) -> etree._Element:
    kind = next(
        t for t in graph.objects(model_group, RDF.type) if t in _MODEL_GROUP_TAG
    )
    group_el = etree.SubElement(parent, f"{{{XS_NS}}}{_MODEL_GROUP_TAG[kind]}")
    for particle in _ordered_particles(graph, model_group):
        _emit_particle(graph, group_el, particle)
    return group_el


def generate_complex_type(graph: Graph, complex_type: URIRef) -> etree._Element:
    """Render a single xsdo:ComplexTypeDefinition's content model as <xs:complexType>."""
    root = etree.Element(f"{{{XS_NS}}}complexType", nsmap={"xs": XS_NS})
    content_model = graph.value(complex_type, XSDO.contentModel)
    _emit_model_group(graph, root, content_model)
    return root
