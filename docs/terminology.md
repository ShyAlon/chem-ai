# Fix-It terminology

The backend catalogs hold reusable aliases for [objects, finishes, and cleaning supplies](../backend/homechem/data/lexicon.json) and [surface materials](../backend/homechem/data/materials.json). [lexicon.py](../backend/homechem/lexicon.py) builds the runtime dictionaries. See the [terms and processes inventory](terms-and-processes-inventory.md) for the full data dictionary and source map. Hebrew questions are translated into English before entering the same [resolver](../backend/homechem/interpretation.py). spaCy extracts grammatical targets and modifiers using the locked small English model. NLTK Snowball reduces English inflections to shared stems; WordNet supplies broad physical-object classes and selected category synonyms. The local lexicon is an application overlay, not an exhaustive object list. The resolver matches the longest terms in each group.

| Field | Example values | Meaning |
| --- | --- | --- |
| `object_type` | `floor`, `sink`, `tabletop` | The thing the user wants to clean |
| `device` | `iphone`, `ipad`, `android` | Device context for a part such as a screen |
| `substrate` | `ceramic`, `glass`, `stainless_steel` | What it is made of |
| `finish` | `glazed`, `uncoated`, `polished` | The surface treatment, when stated |
| `materials` | `not_stated`, `water_and_mop_only`, `unknown` | The proposed cleaning supplies and tools |
| `surface` | `ceramic_tile_floor`, `ceramic_sink`, `unknown` | The candidate reviewed surface used by the policy |

“Ceramic floor” yields object `floor` and substrate `ceramic`. “Porcelain sink” uses the same substrate and object `sink`. The resolver checks that the object and substrate occur together or are joined by a recognized phrase. Incompatible finishes, damage, conflicting terms, or unexplained cleaning product wording keep the procedure unverified. The browser displays recognized fields and includes them in its debug object alongside the original question and any English translation. A screen question with no substrate prompts for the exposed material and finish. The LLM fallback may suggest a surface for unfamiliar wording and leaves cleaning materials unverified.

Add synonyms in the relevant backend catalog and cover the variant in the [resolver tests](../backend/tests/test_interpretation.py). Material labels belong in `materials.json`; other entity labels belong in [labels.json](../backend/homechem/data/labels.json). New reviewed procedures are defined in [procedures.json](../backend/homechem/data/procedures.json), including eligibility, sources, and bilingual instructions. Management validates and exports material and procedure drafts; the import scripts apply them to the repository. Restart the API to load changes.

Device names are recognized as context. A screen recipe is selected from the exposed material and finish. Bare glass on a tabletop and smooth glass over electronics can use different methods because their tolerance for moisture differs.

Specific materials retain their IDs and declared parents (`porcelain` → `ceramic`). Unknown substance modifiers may be enriched with ChEBI candidates via the official OLS MCP service (`terminology.py`). Candidates retain ontology IDs, definitions, and direct parents separately from catalog material identity. Remote results cannot authorize a reviewed procedure. The Data lab exposes explicit terminology search; the trace and console expose automatic enrichment.

Before target classification, nominal-chunk recovery joins adjacent uncoordinated object nouns and recovers noun/verb ambiguities only when an object slot, nominal compound, and physical WordNet noun sense agree. This handles lowercase “apple watch” with or without a question mark without a product alias or capitalization requirement. Conjunctions and punctuation keep separate targets separate.

Task-role normalization distinguishes a problem noun from an affected object using dependency relations and configured WordNet classes. “Clear a clog in the sink” and “remove the blockage from my sink” resolve the sink as the target; action lemmas and problem-class roots are backend data rather than whole-question aliases. Only grammatical problem context is covered, so unrelated targets and chemical terms remain subject to ambiguity and exclusion checks.
