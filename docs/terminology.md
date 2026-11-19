# Fix-It terminology

The [English dictionary](../backend/homechem/lexicon.py) holds reusable aliases for objects, surface materials, finishes, and cleaning supplies. Hebrew questions are translated into English before entering the same [resolver](../backend/homechem/interpretation.py). NLTK Snowball reduces English inflections to shared stems, and selected WordNet senses supply synonyms. The resolver matches the longest terms in each group.

| Field | Example values | Meaning |
| --- | --- | --- |
| `object_type` | `floor`, `sink`, `tabletop` | The thing the user wants to clean |
| `device` | `iphone`, `ipad`, `android` | Device context for a part such as a screen |
| `substrate` | `ceramic`, `glass`, `stainless_steel` | What it is made of |
| `finish` | `glazed`, `uncoated`, `polished` | The surface treatment, when stated |
| `materials` | `not_stated`, `water_and_mop_only`, `unknown` | The proposed cleaning supplies and tools |
| `surface` | `ceramic_tile_floor`, `ceramic_sink`, `unknown` | The candidate reviewed surface used by the policy |

“Ceramic floor” yields object `floor` and substrate `ceramic`. “Porcelain sink” uses the same substrate and object `sink`. The resolver checks that the object and substrate occur together or are joined by a recognized phrase. Incompatible finishes, damage, conflicting terms, or unexplained cleaning product wording keep the procedure unverified. The browser displays recognized fields and includes them in its debug object alongside the original question and any English translation. A screen question with no substrate prompts for the exposed material and finish. The LLM fallback may suggest a surface for unfamiliar wording and leaves cleaning materials unverified.

Add synonyms in the relevant dictionary group and cover the variant in the [resolver tests](../backend/tests/test_interpretation.py). Add new entity labels to the [language catalog](../web/src/i18n.ts). For a new procedure, add its reviewed surface combination and acceptable finishes, link the evidence in the [home solutions catalog](home-solutions.md), and add a corresponding [policy rule](../backend/homechem/policy.py) and localized instructions.

Device names are recognized as context. A screen recipe is selected from the exposed material and finish. Bare glass on a tabletop and smooth glass over electronics can use different methods because their tolerance for moisture differs.
