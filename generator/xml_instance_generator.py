"""A-box graph -> real XML instance document. Sibling to xsd_generator.py's
schema generator: same tree-walk (ComplexTypeDefinition -> Sequence ->
ordered Particles), but each leaf emits a populated data element using a
real value instead of an abstract <xs:element> declaration.
"""
from __future__ import annotations

from lxml import etree
from rdflib import RDF, Graph, Namespace, URIRef

from generator.xsd_generator import XSDO, _ordered_particles

OFR = Namespace("https://openfaster.org/realizations/schema#")


def generate_instance(
    graph: Graph, complex_type: URIRef, values_by_concept: dict[str, str]
) -> etree._Element:
    root = etree.Element("instance")
    content_model = graph.value(complex_type, XSDO.contentModel)

    for particle in _ordered_particles(graph, content_model):
        term = graph.value(particle, XSDO["term"])
        if (term, RDF.type, XSDO.ElementDeclaration) not in graph:
            raise NotImplementedError(f"Only ElementDeclaration particle terms are supported: {term}")

        concept = graph.value(term, OFR.realizesConcept)
        if concept is None or str(concept) not in values_by_concept:
            continue  # not curated, or no value provided -- skip (matches minOccurs=0 fields)

        name = str(graph.value(term, XSDO.name))
        el = etree.SubElement(root, name)
        el.text = values_by_concept[str(concept)]

    return root
