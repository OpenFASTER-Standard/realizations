# Realizations

Part of [OpenFASTER](https://openfaster.org), alongside
[`institutional-ontology`](https://github.com/OpenFASTER-Standard/institutional-ontology),
[`xsd-ontology`](https://github.com/OpenFASTER-Standard/xsd-ontology),
[`spreadsheet-ontology`](https://github.com/OpenFASTER-Standard/spreadsheet-ontology),
and [`xml-ontology`](https://github.com/OpenFASTER-Standard/xml-ontology).

Per-module instance graphs realizing `institutional-ontology` concepts as
`xsd-ontology`/`spreadsheet-ontology` structures, plus the generator code
that turns those graphs into real `.xsd`/`.xlsx`/`.xml` artifacts. This is
where all the domain/module-specific coupling lives — the four ontology
repos above stay fully independent of MiKaDiv/KaFE and of each other.

Licensed [CC BY 4.0](LICENSE).

## Files

- `modules/*.ttl` — per-module structural realizations (`XSDO:`-shaped),
  e.g. `kafe.ttl` for KaFE's real `NatP_Struct`. Owns the `ofr:realizesConcept`
  linking predicate back to `institutional-ontology` concepts.
- `layouts/*.ttl` — per-module canonical Excel layout definitions
  (`SSO:`-shaped), e.g. `layouts/kafe-canonical.ttl`.
- `generator/xsd_generator.py` — graph → XSD schema fragment.
- `generator/xlsx_generator.py` — graph → canonical `.xlsx` template
  (real data-validation dropdowns, sourced from `xsdo:hasEnumerationValue`).
- `generator/xlsx_ingest.py` — `.xlsx` → graph, two steps:
  `extract_raw_cells` (mechanical, structure-agnostic — works on any file)
  and either `interpret_positional` (a single flat sheet's positional
  addressing, producing a real `ofr:FieldObservation` A-box graph) or
  `interpret_master_detail` (a parent/child sheet pair, additionally
  minting the `ofr:partOfRecord`/`recordPosition`/`hasRole` graph — see
  below).
- `generator/xml_instance_generator.py` — `ofr:FieldObservation` graph +
  `XSDO` structure → `XMLO`-shaped graph (`generate_instance`) → real,
  namespace-qualified XML text (`serialize_xmlo_to_xml`).

## The `ofr:` namespace

`https://openfaster.org/realizations/schema#` — small, generic
linking/A-box vocabulary owned by this repo, documented here rather than
in a separately governed `.ofn` file (same informal status
`ofr:realizesConcept` has always had):

- `ofr:realizesConcept` — links a structural node (an `XSDO:
  ElementDeclaration`, an `SSO:DataColumn`, an `XSDO:EnumerationValue`)
  to the `institutional-ontology` concept it realizes.
- `ofr:FieldObservation` / `ofr:aboutRecord` / `ofr:observedConcept` /
  `ofr:hasValue` — the A-box fact-representation pattern, mirroring
  SOSA/SSN's `Observation`/`observedProperty`/`hasSimpleResult` shape
  (real W3C/OGC precedent — see `bulk-platform`'s
  `docs/superpowers/specs/2026-09-01-xml-ontology-and-abox-design.md`).
  `hasValue` accepts either a literal (free-text fields) or an `IO:`
  individual (enumerated fields) — one uniform shape for both.
- `ofr:partOfRecord` / `ofr:recordPosition` / `ofr:hasRole` /
  `ofr:impliesRole` — extend `aboutRecord` so a fact can be tied to a
  specific, uniquely-identified, role-scoped, positionally-indexed
  sub-entity within a repeating structure (e.g. which `Erstattungsantrag`,
  which person role, at what position among up to 500 repetitions), rather
  than one flat undifferentiated record — grounded in real XBRL OIM
  (dimension-set/typed-dimension row-scoping) and RML/R2RML (referencing
  object map join-key) precedent, plus PROV-O's `prov:hadRole` for the role
  shape specifically. `partOfRecord` (sub-entity → parent entity) is
  containment; `recordPosition` (integer) is the 1-based ordinal within a
  *repeating* group only (asserted where real repetition exists, not on
  every level of the hierarchy); `hasRole` (sub-entity → `IO:` role
  individual) is asserted by ingest code from a real value (e.g. an Excel
  Role-column dropdown); `impliesRole` (`XSDO:ElementDeclaration` → `IO:`
  role individual) is asserted once, structurally, in a module's own
  `modules/*.ttl` (e.g. `kafe.ttl`'s `SteuerpflichtigePerson` element
  always implies the taxpayer role) — see `bulk-platform`'s
  `docs/superpowers/specs/2026-09-02-nested-repeating-entity-abox-design.md`.

## Testing

```bash
pip3 install --break-system-packages -r requirements.txt
python3 -m pytest tests/ -v
```
