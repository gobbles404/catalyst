# Golden Rules

Generalized learnings from earlier work, kept as directional defaults: more often right than wrong, and not all of it agreed. Where a rule here conflicts with a tenet in [PRINCIPLES.md](../PRINCIPLES.md), the tenet wins. Rules 1, 2, 3, 5, and 6 have already become tenets there.

## How to use these

These are not style rules. Formatting, imports, and line length belong to the linter; types belong to the checker. What is left over is judgment, and this is the judgment worth writing down.

Read them as defaults with reasons attached. A default can be overruled, but only out loud, in the change that overrules it, with the reason. A rule that gets quietly ignored twice should be deleted or rewritten, not left as decoration.

Three are load-bearing enough to name up front: resolve once, one path, and a missing input fails.

## 1. Meaning

What a trade is gets decided once, early, and everything downstream reads that decision instead of re-deriving it.

1. **Resolve once, then dispatch from the resolution.** Turn authored input into one complete, valid, typed object at the boundary, and let every later layer consume that object. Never rebuild the same decision from route plus source plus model plus schedule plus a string, four layers apart.
2. **Two taxonomies, one connector.** What a trade means economically and how it is physically calculated are separate hierarchies. Connect them with one typed case and one static binding. Do not fuse them into a single inheritance tree, and do not let market data decide which instrument something is.
3. **Contracts are data, not machinery.** The record of what a trade requires holds facts: measures, treatments, requirements, rules. It holds no compiler, kernel, callback, adapter, or cache version. Economic identity must stay independent of whatever implementation currently computes it.
4. **The core has one name for a thing.** The desk has a dozen names for the same instrument. Those names are labels on a sheet. The core gets one curated definition per genuine economic shape, and the aliases stay on the workbook side.
5. **One path. N of one is a group of one.** If a general case exists, the specific case goes through it. No singleton branch, no scalar fallback, no alias, no shim, no second producer for the same product.

## 2. Boundaries

Each layer does one job and trusts the layer beneath it.

6. **Parse at the edge, trust inside.** There is exactly one place where untrusted input becomes typed values: where the worksheet hands them over. Past that line, nothing re-checks a type its caller already established. Normalize in constructors; do not re-verify.
7. **Readers don't calculate. Kernels don't shop.** A reader projects retained state and never prices, never reads current market data. A kernel receives explicit numbers and never parses a row, selects a market, chooses a route, or formats a cell. Collectors compose and never convert kinds.
8. **The workbook experience is a product decision.** Formulas, signatures, worksheet flow, handle placement, and visible defaults are decided by the person who trades with them, not inferred from the Python design. When the intended behavior has not been stated, ask, and record the answer before implementing.
9. **The measuring instrument is not part of the product.** Instrumentation reports counts the code already knows, at a boundary the caller controls. It does not thread collectors through pricing code, does not aggregate history, does not render, and does not become a feature users read.

## 3. Identity and state

What makes two things the same thing, and where state is allowed to live.

10. **Identity is content, never address.** Cache on what a value was built from, not on which object or handle asked for it. A rebuilt-but-identical input hits the cache. Never hash a text rendering, never key on an object address, and stamp the digest once at construction so nothing downstream recomputes it.
11. **No ambient state.** Every producer names its complete inputs. No global fallback market, no implicit clock, no singleton collection, no context variable a function reads behind the caller's back, no module that must be imported first for another to work.
12. **Explicit beats inferred.** The engine does not accept a mixed bag and silently partition it into things it can handle. The caller states what belongs together; the engine validates that claim and fails on the first real violation.
13. **Labels are provenance, not identity.** A name, a sheet path, a trade id, a display label: these travel with a result so a human can trace it. None of them participate in economic identity or cache keys.
14. **Immutable after publication, mutable never.** Objects that cross a boundary are built frozen and stay frozen. Do not maintain a mutable convenience regime alongside a frozen published one, and do not deep-copy graphs to make one safe from the other.

## 4. Numbers

This is a pricing library. A number without its unit, basis, and provenance is not a result.

15. **A missing input fails. It is never substituted.** Absent market data raises, loudly, naming what is missing and for which instrument. Never a default, never a neighbour's file, never a fabricated value that lets a load succeed.
16. **Say the unit, the basis, the treatment, the sign.** Every quantity carries its unit; every price says whether it is quote or base; every time says its day count; every value says cash or mark; every position carries direction in its sign. Where two are legitimately different, keep them separate and name both.
17. **Price the group, not the occurrence.** The unit of calculation is a compatible group under a scenario set, evaluated in one pass over arrays. A single trade is that call with one member. Per-occurrence loops inside a kernel are a defect, not a style.
18. **Numbers move for one stated reason.** When a change moves a result, the change explains it in one sentence, bounds the movement, and shows that structure, ordering, states, and failure behavior are untouched. Anything systemic, unexplained, or non-finite is a product decision, not a refactor.
19. **"Did it change?" and "is it right?" are different questions.** Regression testing detects movement. Model validation establishes correctness. They need different instruments, different evidence, and different reviewers. Never let a snapshot of your own output become the definition of correct.
20. **Invariants outlive baselines.** Alongside snapshots, assert the things that must be true of any correct implementation: put-call parity, straddle equals call plus put, American at least European at least intrinsic, monotonicity in volatility, additivity across buckets. These survive a regeneration; a snapshot does not.

## 5. Change

How things get replaced.

21. **Cut over. Do not accrete.** When a change replaces a name, a signature, a schema, or a formula, remove the old path and let stale callers fail clearly. Aliases, shims, ignored parameters, dual names, and migration periods exist only when the product owner requires them and the ticket records their exact scope and end date.
22. **Retire in sequenced slices, each one mergeable.** Big removals go: move every caller, delete each legacy route as its last user leaves, shrink the list of known exceptions to zero, then delete the thing itself. Every step is independently reviewable and independently shippable.
23. **Name what you are not doing.** Every ticket and every pull request states its non-goals explicitly. Not "out of scope for now" but the specific things a reader might reasonably expect and will not find.
24. **Behavior and its baseline never move together.** A change may alter the code or the expected outputs, never both. Land the behavior, let the comparison fail and say exactly what moved, then regenerate in a separate reviewed change that carries the explanation.
25. **A version marks an independently loadable state.** Bump when a user or operator can load something different, and record a concrete migration or explicitly record "none". Documentation, tests, fixtures, and closeout records are not loadable artifacts and do not consume a version.
26. **Fail atomically, at the first useful error.** A failed operation leaves nothing staged: no half-published handle, no committed cache entry, no partial result. The message names the occurrence, the stage, and the cause, in the order a user can act on.

## 6. Evidence

What counts as knowing something, as opposed to believing it.

27. **Baseline before you touch it.** Record current behavior before editing: the relevant test, golden, timing, or count. Name every already-failing thing out loud first, so it cannot later be mistaken for a regression or waved away as one.
28. **Measure counts before time.** Performance claims are made in deterministic units: how many times the kernel ran, how many market reads, how many allocations, how many calls. Those are identical on every machine and can be asserted exactly. Wall clock is a record you keep, not a gate you set.
29. **Measured, not estimated.** Coverage, cost, size, and reach are numbers you produced, not adjectives you chose. If a claim about the system cannot be reproduced by a command, it is a hypothesis.
30. **Passing tests are evidence, not acceptance.** Green means nothing detected. Whether the thing does what the desk needed is a separate judgment made by the person who asked for it, in the workbook, before it is done.

## 7. Judgment

The rules about the rules.

31. **Guidance is a harness, not a cage.** When a rule, a document, or a process is stale, contradictory, or is about to make the work worse, say so with the specific conflict and propose the smallest correction. Never silently ignore it, and never force a bad solution to satisfy it.
32. **Balk before you build on a bad premise.** If the request rests on a false assumption or a missing decision, stop before modifying production code and return it with the concrete finding. That is a normal correction, not a failure. Do not repair a definition gap by quietly inventing requirements in code.
33. **Name the mode before you act.** Exploring, capturing, shaping, prioritizing, authorizing, maintaining, and validating are seven different activities. Most confusion between a person and an agent is one of them being mistaken for another. Say which one you are in.
34. **Build for the second consumer, not the imagined tenth.** Generality is earned by a real second caller. Until one exists, write the specific thing. Bounds, budgets, transactions, and abstractions are added when a measurement or an incident demands them.
35. **Prefer the boring dependency to the clever internal.** If a competent library does it, take the library and spend the attention on the pricing. Write it yourself only when nothing does it, when the thing is small enough to read in one sitting, and when you can state the ceiling it will never grow past.

## The anti-principles

These all looked like good engineering at the time. None of them announce themselves. Each is stated as the seductive version first, because that is the form in which it will arrive.

- **A1. "Make it safe by checking everywhere."** Validating in every constructor and at every call feels like defense in depth. It is the same check written many times, none of which catches a bug the type checker would not, and all of which must be edited when a rule changes.
- **A2. "Store it compactly to save memory."** Hand-packed byte buffers with dictionary-coded columns and framed hashes look disciplined. In Python they are slower and bigger than an array, and the readers rebuild the objects on every access anyway, so the compaction only holds while nobody looks.
- **A3. "Identity from a text rendering."** Hashing a canonical string of an object's fields is easy to implement and easy to debug. It is also slow, fragile to formatting, and tempting to recompute wherever it is needed rather than carry.
- **A4. "Keep the old path until everyone migrates."** A shim is kindness to callers. It is also a second implementation that must be tested, kept correct, and eventually removed by someone who no longer remembers why it exists.
- **A5. "Ship the measurement so users can see it."** A performance surface in the product sounds like transparency. It puts instrumentation in the hot path, makes the observer part of the contract, and produces numbers that need a manual to interpret.
- **A6. "Support reloading so the loop is fast."** Hot reload inside a long-lived host seems worth some care. That care metastasizes: every module grows a list of retired names to purge, the runtime carries its own history, and import order becomes load-bearing.
- **A7. "Test that the retired thing is really gone."** Asserting absence feels like completing a cutover. It is a test that can only ever pass, that grows with every removal, and that documents history rather than behavior.
- **A8. "Generalize now, while the pattern is fresh."** Extracting a template from the second implementation is usually right. Stamping that template into every family before the shared behavior is known produces the same fifteen slots repeated, where changing one shared rule means seven edits.
- **A9. "Two surfaces, one core."** Serving a Python API and a workbook from the same core sounds like leverage. It doubles the mutability regimes, the validation, the tests, and the vocabulary, and neither surface ends up shaped for its user.
- **A10. "Decide the platform question later."** Deferring a load-bearing choice keeps options open. It also means every layer above it is built twice or built vaguely, and the deferral quietly becomes the decision.
- **A11. "Write it down so we remember why."** Recording decisions is genuinely valuable, which is what makes the excess hard to see. Prose that outgrows the code, and tests that enforce the shape of prose, turn documentation into a maintenance surface of its own.
- **A12. "Make it load; we'll fix the data later."** A plausible stand-in for missing data unblocks today's work. It then becomes invisible, because nothing fails, and the wrongness is discovered by an auditor rather than by a test.

## When rules conflict

They will. "Cut over, do not accrete" and "retire in sequenced slices" pull in opposite directions on any given day; so do "build for the second consumer" and "resolve once". The order of precedence when two collide:

| Order | Wins | Because |
|---|---|---|
| 1 | A wrong number never ships | Everything else is recoverable. Rules 15, 19, and 20 outrank the rest without argument. |
| 2 | The desk's stated need | Rule 8. The workbook experience is not ours to infer, and a technically superior surface nobody can use is a failure. |
| 3 | Reversibility | Prefer the choice that is cheaper to undo. Deleting is reversible through git; a shipped compatibility promise is not. |
| 4 | The simpler thing that works now | Rule 34. When two designs are otherwise tied, take the one with less in it. |
| 5 | Consistency with what exists | Last, not first. Matching a bad existing pattern is how a bad template gets its seventh copy. |

The single sentence, if only one survives: resolve meaning once, keep one path, fail loudly on missing input, and let the numbers be the evidence.
