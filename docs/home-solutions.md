# HomeChem home solutions

Fix-It selects a reviewed procedure from the exposed material, its finish, its use context, and the cleaning supplies. An electronic screen needs different moisture handling than a tabletop even when both have glass surfaces.

| Surface | Reviewed scope |
| --- | --- |
| [Smooth glass screen](#smooth-glass-screen) | Dry dust removal from intact smooth glass over electronics |
| [Glass tabletop](#glass-tabletop) | Routine cleaning of intact, uncoated glass |
| [Glazed ceramic sink](#glazed-ceramic-sink) | Everyday cleaning of intact glazed ceramic |
| [Glazed ceramic tile floor](#glazed-ceramic-tile-floor) | Routine damp mopping of intact glazed ceramic or porcelain |

## Smooth glass screen

Confirm the exposed glass is intact and smooth, with no protector or special finish. Power off and disconnect the device. Gently lift loose dust with a clean, dry microfiber cloth.

The fibers pick up particles through contact. Dry wiping avoids adding a liquid that can wick into openings or a solvent that can interact with the finish. [American Cleaning Institute screen care](https://www.cleaninginstitute.org/cleaning-tips/work/clean-desk-computer)

## Glass tabletop

Lightly dampen a clean microfiber cloth and wipe intact, uncoated glass. Dry with a separate clean cloth.

Polar water dissolves some residues, including salts. Drying removes droplets before evaporation leaves dissolved minerals on the glass. [Documentary Heritage and Preservation Services guide](https://dhpsny.org/blog/dhps-tips-recommended-cleaning-products-collections-spaces)

## Glazed ceramic sink

For routine dirt on intact glaze, wipe with warm water, mild dish detergent, and a soft cloth. Rinse thoroughly and dry.

Detergent surfactants have parts that associate with grease and parts that interact with water. They help disperse greasy dirt so the rinse can remove it along with detergent residue. [Glazed ceramic care](https://www.ohiohistory.org/historic-housekeeping-glass-and-ceramics/) · [The chemistry of cleaning](https://www.cleaninginstitute.org/understanding-products/science-soap/chemistry-cleaning)

## Glazed ceramic tile floor

Sweep up loose grit, then damp-mop with clean water. Remove standing water and let the floor dry.

Sweeping removes particles that can abrade the glaze. Water dissolves some polar residues and a damp mop picks up other particles. [Porcelain and ceramic tile care](https://www.arizonatile.com/resources/care-maintenance/care-maintenance-for-porcelain-and-ceramic/)

## Adding a solution

Record the substrate, finish, use context, supplies, procedure, and chemistry or physical mechanism. Add evidence that covers the material and method. Include a calculation when quantities matter. Link the [policy rule](../backend/homechem/policy.py) and its localized instructions.

## Additional implemented workspaces

Select a workspace above the notebook to test its supported scenario. English and Hebrew content is bundled in `backend/homechem/data/scenarios.json`.

| Workspace | Implemented scope |
| --- | --- |
| Stain removal | Fresh coffee on washable cotton, with care-label checks |
| Food science | Separation of an oil-and-water dressing |
| Limescale and corrosion | Explanation of white deposits after heating hard water and distinction from corrosion |
| Material care | Acidic-food container compatibility considerations |
| Water chemistry | Hardness classification from mg/L as CaCO₃, including decimal values |
| Home experiments | Paired stirred and unstirred sugar dissolution times and their ratio |
| Product-label explanations | Selectable surfactant, enzyme, and builder explanations |
| Chemical disposal | Leftover-paint identification and referral to local collection services |

Each scenario includes a chemistry explanation and a source link. Disposal collection locations are determined by the local authority. The free-text interpreter remains scoped to the four cleaning procedures.

Run `./scripts/test-use-cases.sh` to check both languages and the calculators against an isolated API server. Set `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH` to an installed Chromium-compatible browser if the Playwright browser is unavailable.

## Procedure definitions

Procedure definitions are maintained in `backend/homechem/data/procedures.json`. Each entry owns the recognized object/material relationship, compatible finishes, cleaning supply set, bilingual instructions and confirmations, chemistry explanation, evidence, and question hint. Management can validate and export this catalog. Apply an export with `./scripts/import-procedures.sh <file>` and restart the API.

React receives confirmation fields and assessment actions from interpretation, and instructions from assessment. Adding a procedure that uses the existing matching and assessment algorithms requires a catalog edit.
