# Consolidation follow-ups

Pinned on 26 September 2026. These are pending decisions and implementation work, not changes made by the index/calendar refactor. The linked function pages remain the authoritative specifications.

- **Index conventions: validate codes and unit compatibility before pricing consumes them.** Check supported quantity categories, currency units and quantity units, including compatibility between quotation and quantity units. Different compatible units must remain usable. Specify the behavior and exact errors in [index-conventions.md](index-definitions/index-conventions.md), then implement the checks once in the conventions creator.
- **Contract specifications: settle and enforce the remaining business rules before pricing consumes them.** Decide the positive lot-size requirement, treatment of negative fees/rebates, and the currency or unit of each fee. Unique names and whole-number lot sizes are already checked. Specify the remaining rules and exact errors in [contract-specifications.md](index-definitions/contract-specifications.md), then implement the appropriate checks in the specifications creator. Cross-object interpretation belongs to its consumer; do not guess a fee currency.

Neither item belongs on the live market update path. No automatic implementation or schedule is requested.
