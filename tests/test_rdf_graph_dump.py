"""Unit tests for the generic RDF-triple-dump exporter against small,
hand-built graphs -- not the real fixture (that's covered by
test_export_showcase_data.py's integration-level assertions in Task 2)."""
from rdflib import BNode, Graph, Literal, Namespace, RDF, RDFS, URIRef
from rdflib.namespace import OWL

from generator.rdf_graph_dump import dump_graph, node_id

EX = Namespace("https://example.org/ex#")


def _by_id(nodes):
    return {n["id"]: n for n in nodes}


def test_iri_and_literal_nodes_get_real_identifiers_as_labels():
    g = Graph()
    g.bind("ex", EX)
    g.add((EX.alice, EX.hasName, Literal("Alice")))

    result = dump_graph(g)

    nodes = _by_id(result["nodes"])
    assert nodes[str(EX.alice)] == {"id": str(EX.alice), "label": str(EX.alice), "kind": "iri"}
    lit_id = node_id(Literal("Alice"))
    assert nodes[lit_id]["kind"] == "literal"
    assert nodes[lit_id]["label"] == '"Alice"'
    assert result["edges"] == [{"source": str(EX.alice), "target": lit_id, "label": "ex:hasName"}]


def test_blank_nodes_render_as_real_turtle_blank_node_syntax():
    g = Graph()
    bnode = BNode()
    g.add((EX.alice, EX.hasObservation, bnode))
    g.add((bnode, EX.hasValue, Literal("x")))

    result = dump_graph(g)

    nodes = _by_id(result["nodes"])
    expected_id = f"_:{bnode}"
    assert expected_id in nodes
    assert nodes[expected_id] == {"id": expected_id, "label": expected_id, "kind": "blank"}
    assert node_id(bnode) == expected_id


def test_repeated_literal_value_is_one_shared_node_not_two():
    g = Graph()
    g.add((EX.alice, EX.anrede, Literal("HERR")))
    g.add((EX.bob, EX.anrede, Literal("HERR")))

    result = dump_graph(g)

    literal_nodes = [n for n in result["nodes"] if n["kind"] == "literal"]
    assert len(literal_nodes) == 1
    assert len(result["edges"]) == 2


def test_literals_with_different_datatypes_are_distinct_nodes():
    g = Graph()
    g.add((EX.alice, EX.stringValue, Literal("2")))
    g.add((EX.alice, EX.intValue, Literal(2)))

    result = dump_graph(g)

    literal_nodes = [n for n in result["nodes"] if n["kind"] == "literal"]
    assert len(literal_nodes) == 2


def test_structural_only_keeps_hierarchy_predicates_and_drops_others():
    g = Graph()
    g.add((EX.Cell, RDF.type, OWL.Class))
    g.add((EX.HeaderCell, RDFS.subClassOf, EX.Cell))
    g.add((EX.HeaderCell, RDFS.comment, Literal("A cell that is a header.")))

    result = dump_graph(g, structural_only=True)

    edge_labels = {e["label"] for e in result["edges"]}
    assert "rdfs:comment" not in edge_labels
    assert any(e["source"] == str(EX.HeaderCell) and e["target"] == str(EX.Cell) for e in result["edges"])


def test_structural_only_drops_owl_meta_type_triples():
    g = Graph()
    g.add((EX.Cell, RDF.type, OWL.Class))

    result = dump_graph(g, structural_only=True)

    assert result["nodes"] == []
    assert result["edges"] == []


def test_structural_only_uses_rdfs_label_falling_back_to_local_name():
    g = Graph()
    g.bind("ex", EX)
    g.add((EX.HeaderCell, RDFS.subClassOf, EX.Cell))
    g.add((EX.HeaderCell, RDFS.label, Literal("Header Cell")))

    result = dump_graph(g, structural_only=True)

    nodes = _by_id(result["nodes"])
    assert nodes[str(EX.HeaderCell)]["label"] == "Header Cell"
    assert nodes[str(EX.Cell)]["label"] == "Cell"  # no rdfs:label -- falls back to local name


def test_edge_labels_use_bound_prefix_or_fall_back_to_local_name():
    g = Graph()
    g.bind("ex", EX)
    g.add((EX.alice, EX.hasName, Literal("Alice")))
    unbound = Namespace("https://unbound.example.org/")
    g.add((EX.alice, unbound.mystery, Literal("y")))

    result = dump_graph(g)

    edge_labels = {e["label"] for e in result["edges"]}
    assert "ex:hasName" in edge_labels
    assert "mystery" in edge_labels
