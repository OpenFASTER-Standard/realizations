"""Generic RDF-triple-dump exporter, shared by every graph the showcase
renders (SSO/A-box/XMLO pipeline stages, plus the architecture layer's
per-repo ontology graphs) so there is exactly one place that decides how a
real RDF term becomes a Sigma.js node/edge, not N hand-picked copies that
can drift out of sync with each other.
"""
from __future__ import annotations

from rdflib import BNode, Graph, URIRef
from rdflib.namespace import OWL, RDF, RDFS

_STRUCTURAL_PREDICATES = {RDF.type, RDFS.subClassOf, RDFS.subPropertyOf, RDFS.domain, RDFS.range}

# Boilerplate rdf:type targets every OWL file repeats for every class/
# property/individual declaration -- real, but not per-ontology content;
# excluded only when structural_only=True so the architecture-layer
# ontology graphs show the real class/property hierarchy, not a hub node
# every declaration points at.
_OWL_META_TYPES = {
    OWL.Class,
    OWL.ObjectProperty,
    OWL.DatatypeProperty,
    OWL.AnnotationProperty,
    OWL.NamedIndividual,
    OWL.Ontology,
    RDF.Property,
}


def node_id(term) -> str:
    """The real, stable identifier a term renders as everywhere -- also
    used directly by export_showcase_data.py to compute a stage's
    highlightId so it always names an id dump_graph will actually produce.
    """
    if isinstance(term, BNode):
        return f"_:{term}"
    if isinstance(term, URIRef):
        return str(term)
    return f"lit:{term.n3()}"


def _local_name(iri: str) -> str:
    return iri.rsplit("#", 1)[-1].rsplit("/", 1)[-1]


def _qname(g: Graph, term: URIRef) -> str:
    try:
        prefix, _, local = g.namespace_manager.compute_qname(str(term), generate=False)
        return f"{prefix}:{local}" if prefix else local
    except KeyError:
        return _local_name(str(term))


def _node_entry(term, *, structural_only: bool, g: Graph) -> dict:
    ident = node_id(term)
    if isinstance(term, BNode):
        return {"id": ident, "label": ident, "kind": "blank"}
    if isinstance(term, URIRef):
        if structural_only:
            label = g.value(term, RDFS.label)
            label = str(label) if label is not None else _local_name(ident)
        else:
            label = ident
        return {"id": ident, "label": label, "kind": "iri"}
    return {"id": ident, "label": f'"{term}"', "kind": "literal"}


def dump_graph(g: Graph, *, structural_only: bool = False) -> dict:
    """Every real triple in g becomes a node/edge pair: each unique
    subject/object a node (real RDF term identity -- a literal value
    repeated across multiple triples is genuinely the same term, and
    renders as one shared node, not a display artifact), each predicate an
    edge label. structural_only restricts to rdf:type/rdfs:subClassOf/
    rdfs:subPropertyOf/rdfs:domain/rdfs:range (dropping rdfs:comment/
    IAO_0000115-style prose annotations that would otherwise dominate an
    ontology's real class/property graph) and drops rdf:type edges whose
    object is OWL/RDFS declaration boilerplate (owl:Class etc.) rather
    than real per-ontology content; node labels prefer rdfs:label,
    falling back to the IRI's local name.
    """
    nodes: dict[str, dict] = {}
    edges = []
    for s, p, o in g:
        if structural_only:
            if p not in _STRUCTURAL_PREDICATES:
                continue
            if p == RDF.type and o in _OWL_META_TYPES:
                continue
        s_entry = _node_entry(s, structural_only=structural_only, g=g)
        o_entry = _node_entry(o, structural_only=structural_only, g=g)
        nodes.setdefault(s_entry["id"], s_entry)
        nodes.setdefault(o_entry["id"], o_entry)
        edges.append({"source": s_entry["id"], "target": o_entry["id"], "label": _qname(g, p)})
    return {"nodes": list(nodes.values()), "edges": edges}
