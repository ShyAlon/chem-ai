# Free object-to-material source evaluation

The application compares free APIs through one backend adapter. Data is retrieved dynamically; this document records observations, not a product/material catalog.

| Provider | Interface | Material evidence | Limitations |
| --- | --- | --- | --- |
| Wikidata | Action API: label search, entity claims, batched labels | `P186` made from material; `P518` applies-to-part qualifier; `P854` source URLs | Sparse composition data; search can return unrelated entities and product families. No automatic first-result selection. |
| DBpedia | Public SPARQL endpoint, exact English label variants | Explicit ontology or infobox `material` predicates | Incomplete infobox coverage; exact labels can miss names; availability varies. Based on Wikipedia, so not independent evidence from it. |

Sources: [Wikidata data access](https://www.wikidata.org/wiki/Help:Data_access), [made from material](https://www.wikidata.org/wiki/Property:P186), [DBpedia public SPARQL](https://www.dbpedia.org/resources/sparql/).

## Initial live sample — 2026-11-20

One uncached lookup per query/provider; these observations are not an SLA or a broad coverage benchmark.

| Query | Wikidata | DBpedia |
| --- | --- | --- |
| Apple Watch | Entity candidates, no explicit material claims; 795 ms | Entity candidate, no explicit material claims; 235 ms |
| spoon | Ambiguous entities including a utensil, band and surname; no material claims; 727 ms | Spoon entity, no material claims; 96 ms |
| steel wool | Entity candidates, no explicit material claims; 565 ms | HTTP failure; 102 ms |
| pencil | Wood and graphite claims on the pencil entity; 1085 ms | Entity candidate, no explicit material claims; 349 ms |
| paper clip | Steel on the paper-clip entity; unrelated artwork candidates also returned; 777 ms | Entity candidates, no explicit material claims; 84 ms |
| tennis ball | Entity candidates, no explicit material claims; 488 ms | HTTP failure; 98 ms |

Wikidata provided explicit claims for relevant entities in two of these six queries; DBpedia provided none and failed twice. This small sample favors Wikidata for material evidence and DBpedia as an experimental comparison source. Both can help identify objects, but neither is sufficient for general component-level material resolution. Apple Watch remains unresolved as a material: a product family alone cannot establish the exposed component, exact model, or coating. More evidence providers can implement the same adapter contract.

Reproduce with `./scripts/object-materials-smoke.sh`. Supply your own English queries as arguments to compare further cases. The Data lab offers the same comparison with per-source statuses and timing; activity ZIP exports preserve the associated exchange and diagnostics.
