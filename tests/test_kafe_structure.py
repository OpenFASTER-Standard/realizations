"""Structural smoke test for kafe.ttl's real, positionally-faithful
repeating/role structure -- not full generation, just confirms the shape
Tasks 3-9 build on is actually present and correctly typed.
"""
from rdflib import RDF, Namespace, URIRef

from generator.xsd_generator import XSDO, load_graph

KAFE = Namespace("https://openfaster.org/kafe/schema#")
OFR = Namespace("https://openfaster.org/realizations/schema#")
IO = "https://purl.openfaster.org/io/IO_"


def test_kafe_ctype_has_bevollmaechtigteperson_then_antraege_in_real_order():
    g = load_graph("modules/kafe.ttl")
    content = g.value(KAFE.KAFE_CType, XSDO.contentModel)
    particles = sorted(
        g.objects(content, XSDO.hasParticle),
        key=lambda p: int(g.value(p, XSDO.particlePosition)),
    )
    terms = [g.value(p, XSDO["term"]) for p in particles]
    assert terms == [KAFE.KAFE_BevollmaechtigtePerson, KAFE.KAFE_Antraege]
    assert g.value(KAFE.KAFE_BevollmaechtigtePerson, OFR.impliesRole) == URIRef(f"{IO}0000010")


def test_erstattungsantrag_particle_has_real_maxoccurs_500():
    g = load_graph("modules/kafe.ttl")
    content = g.value(KAFE.Antraege_CType, XSDO.contentModel)
    particles = list(g.objects(content, XSDO.hasParticle))
    assert len(particles) == 1
    assert g.value(particles[0], XSDO["term"]) == KAFE.Antraege_Erstattungsantrag
    assert int(g.value(particles[0], XSDO.maxOccurs)) == 500
    assert g.value(KAFE.Antraege_Erstattungsantrag, XSDO["type"]) == KAFE.Erstattungsantrag_CType


def test_allgangaben_role_paths_imply_the_right_roles():
    g = load_graph("modules/kafe.ttl")
    assert g.value(KAFE.AllgAngaben_SteuerpflichtigePerson, OFR.impliesRole) == URIRef(f"{IO}0000008")
    assert g.value(KAFE.AllgAngaben_GesetzlicheVertretung, OFR.impliesRole) == URIRef(f"{IO}0000009")
    # StpflPerson_Struct -> StpflNatP_Struct -> NatP -> NatP_Struct, the one
    # role path with an extra nesting level versus GesetzlicheVertretung/
    # BevollmaechtigtePerson's direct NatP_Struct wrap.
    stpfl_content = g.value(KAFE.StpflPerson_Struct, XSDO.contentModel)
    stpfl_particle = next(iter(g.objects(stpfl_content, XSDO.hasParticle)))
    assert g.value(stpfl_particle, XSDO["term"]) == KAFE.StpflPerson_NatuerlichePerson
    assert g.value(KAFE.StpflPerson_NatuerlichePerson, XSDO["type"]) == KAFE.StpflNatP_Struct
    natp_content = g.value(KAFE.StpflNatP_Struct, XSDO.contentModel)
    natp_particle = next(iter(g.objects(natp_content, XSDO.hasParticle)))
    assert g.value(natp_particle, XSDO["term"]) == KAFE.StpflNatP_NatP
    assert g.value(KAFE.StpflNatP_NatP, XSDO["type"]) == KAFE.NatP_Struct


def test_gesetzlichevertretung_wraps_natp_struct_directly():
    g = load_graph("modules/kafe.ttl")
    content = g.value(KAFE.GesetzlicheVertretung_Struct, XSDO.contentModel)
    particle = next(iter(g.objects(content, XSDO.hasParticle)))
    assert g.value(particle, XSDO["term"]) == KAFE.GesetzlicheVertretung_NatuerlichePerson
    assert g.value(KAFE.GesetzlicheVertretung_NatuerlichePerson, XSDO["type"]) == KAFE.NatP_Struct


def test_person_rolle_enum_resolves_all_three_roles():
    g = load_graph("modules/kafe.ttl")
    tokens = {
        str(g.value(v, XSDO.literalValue)): str(g.value(v, OFR.realizesConcept))
        for v in g.objects(KAFE.PersonRolle_ENUM, XSDO.hasEnumerationValue)
    }
    assert tokens == {
        "STEUERPFLICHTIGE_PERSON": f"{IO}0000008",
        "GESETZLICHE_VERTRETUNG": f"{IO}0000009",
        "BEVOLLMAECHTIGTE_PERSON": f"{IO}0000010",
    }
