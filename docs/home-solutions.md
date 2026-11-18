# HomeChem home solutions

This catalog tracks household problems for Fix-It. An available entry has a reviewed procedure and a corresponding policy rule. Draft entries are candidates for future coverage.

| Household problem | Current scope | Status |
| --- | --- | --- |
| [Clean a Studio Display](#clean-a-standard-glass-apple-studio-display) | Apple Studio Display with standard glass | Available |
| Window streaks | Identify the glazing and any coating before selecting a procedure | Draft |
| Limescale on fixtures | Identify the fixture material and finish, then check the manufacturer’s care instructions | Draft |

## Clean a standard-glass Apple Studio Display

**Applies to.** A confirmed Apple Studio Display with standard glass. The app asks the user to confirm the surface and materials before checking the procedure. Nano-texture glass and unidentified displays fall outside this rule.

**Materials.** Water and a clean microfiber cloth.

**Procedure.** Lightly dampen the cloth with water, then wipe the standard glass with it.

**Why it works.** Water helps loosen water-soluble residue. The cloth picks up particles as it passes over the surface.

**Source and app references.** [Apple’s Studio Display cleaning guide](https://support.apple.com/en-gb/guide/studio-display/apd1cf09caf2/2026/mac/27), [policy rule `studio_display_water_cleaning`](../backend/homechem/policy.py), and [English and Hebrew procedure text](../web/src/i18n.ts).

## Adding a solution

Record the problem, supported surfaces and materials, procedure, chemistry explanation, exclusions, and sources. Include the calculation and its inputs when the procedure depends on quantities. When a solution becomes available, link its policy rule, localized procedure, and coverage for supported and unverified inputs.
