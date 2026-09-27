# Consolidation follow-ups

Two pieces of work pinned on 26 September 2026, after the index and calendar consolidation, to settle before pricing consumed the index conventions and the contract specifications. Both are done, in #110, and nothing on this page is outstanding. The function pages are the specifications; this page keeps what was asked and where it was answered, so that neither is raised again from memory.

## Done

| Pinned on 26 September 2026 | Resolved |
|---|---|
| **Index conventions: validate codes and unit compatibility before pricing consumes them.** Check supported quantity categories, currency units and quantity units, including compatibility between quotation and quantity units. Different compatible units must remain usable. Specify the behavior and exact errors in the conventions' page, then implement the checks once in the conventions creator. | In #110: five rules in the creator, the two currency units, the quantity type, then the two quantity units judged by it, with their messages on [index-conventions.md](index-definitions/index-conventions.md). Different units of one category, cents per gallon quoted and dollars per barrel settled, stay usable, and the factor between them is the instrument's to look up. |
| **Contract specifications: settle and enforce the remaining business rules before pricing consumes them.** Decide the positive lot-size requirement, treatment of negative fees or rebates, and the currency or unit of each fee; unique names and whole-number lot sizes were already checked. Specify the remaining rules and exact errors in the specifications' page, then implement the checks in the specifications creator. Cross-object interpretation belongs to its consumer; do not guess a fee currency. | In #110: a lot size of 1 or more, a fee of 0 or more, a rebate never a negative fee, and the fees stated as costs per lot in the index's settlement currency, which nothing checks, with the messages on [contract-specifications.md](index-definitions/contract-specifications.md). Since #115 each row also names its lot's unit, checked against the unit tables by the creator and against the conventions' quantity type by the [index](index-definitions/index.md), the one rule across the two, held where the conventions and the specifications meet. |

Every one of these rules runs when its object is created, and none is on the live market update path, as the pin asked.

## Outstanding

None from this list. What the two pages leave to the first instrument that consumes them, the price scale between the conventions' units, a lot's conversion to the index's quantity unit and the charging of a fee, is under Not here on [index-conventions.md](index-definitions/index-conventions.md) and [contract-specifications.md](index-definitions/contract-specifications.md), for that instrument's page to decide.
