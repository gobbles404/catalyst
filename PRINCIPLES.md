# Principles

## Why this exists

Alignment is everything. A person and an agent build a better product when their vectors point the same way, and this file is where the direction is written down. The rules in AGENTS.md derive from these tenets. When no rule applies, or a rule and a tenet conflict, the tenet decides. This file changes only in a pull request that changes nothing else.

**Surface the fork.** When a path is possible but conflicts with a tenet or a rule, or two tenets conflict, stop and present the choice before taking either path: what is possible, what it conflicts with, and a recommendation. A silent choice is a failure of alignment even when it complies. Present it in conversation before the work, and record it in the pull request under "Conflicts".

**Direction, not mechanism.** A tenet decides direction and never mechanism. If an item names a mechanism, a check, an Excel behavior, a file, or a number, it is design and lives elsewhere.

## Tenets

Each is a tie-break, stated with what it costs.

### 1. Excel is the client

Not one client among several. The pricing code stays separate from the Excel add-in and meets it at one narrow seam, the single place where Excel and Python talk, so pricing can be tested and reasoned about without Excel running, not so another surface can use it. Parse at the edge, trust inside: the seam is the one place where untrusted input becomes typed values, and past it nothing re-checks what its caller already established. Resolve once, then dispatch from the resolution: input becomes one complete, valid, typed object at the seam, and every later layer consumes that object instead of re-deriving the decision from pieces.

Cost: an internal bug travels further before it is caught, and Excel ergonomics are built one at a time as needed.

### 2. Fail loudly. Trust is the product

A wrong number that looks right is the worst outcome, worse than no number. Every failure is visible in the cell and carries what an engineer needs to act: the function, the exception type, the message. The user may hand it to an engineer; that is the audience. No guessing on the user's behalf: extending a curve past its last point, forcing a value back into range, a calculation that stops before it finishes, a stale input are failures, not warnings. A strike outside the range we have data for fails. A hang is a failure. Loading the add-in and the first calculation get grace; after that, none.

Cost: more errors on the sheet than a tool that guesses, and some formulas other libraries would price will not price here.

### 3. Less. Once. Faster

In that order, under trust. First ask whether the work is needed at all. Then whether it was already done. Only then how fast it runs. Never at the expense of a correct number or a visible failure. One path: if a general case exists, the specific case goes through it. N of one is a group of one.

Cost: features arrive later, and caching is held to the same trust bar as the pricing math.

### 4. No backwards compatibility. We use what we ship

Switch everyone at once and let anything old fail loudly, a saved workbook included. Code kept around so old formulas keep working becomes smell and drift. This is safe because the project is not an SDK, a code library for other programmers: nobody calls our code but Excel.

Cost: the workbooks we keep move with the code, every time.

### 5. Words mean things

A name that is approximately right is wrong. Rename before extending. Delete a word when its meaning is gone. Never let a euphemism stand in for a fact: a "warning" is a guess, #N/A is not "the math failed", a blank is not an error.

Plain words over jargon. A term of art is defined the first time it appears, and an example beats a definition. This holds for names in code, for what a user reads in a cell, and for how we talk to each other.

Cost: renaming churns files, and explaining takes longer than assuming.

### 6. One job per thing

Function, module, worksheet function, pull request. When a change would give a thing a second job, split first, in its own commit. Adding to the nearest existing function is the path of least resistance and the most common way code drifts. One-way imports, where the pricing code never depends on the Excel-facing code, is this tenet applied to files.

Cost: more pieces and more seams.

### 7. Contracts are data, not machinery

What a trade means economically is a record of facts: what it is, what it requires, how it is treated. How it gets priced is separate machinery. The two meet at one point. Market data never decides what a trade is, and nothing about how a trade is computed lives in its record.

Cost: a layer between the record and the code that prices it, and two vocabularies to keep in step.

### Confirmed, to be written with the measurement topic

Same inputs, same outputs is a hard guarantee.

## Non-goals

Not an SDK, a code library for other programmers. Nothing outside this repo calls our Python. Nothing is published, internal names carry no promise, and no generality is bought in advance.

## How this file is used

- AGENTS.md points here with the precedence line above.
- A pull request cites the tenet that decided a hard call and lists the conflicts it surfaced.
- A tenet never cited in twenty pull requests is cut or sharpened.
- Amendments are their own pull request.
- [docs/golden-rules.md](docs/golden-rules.md) holds generalized learnings from earlier work, kept as directional defaults. When one conflicts with a tenet, the tenet wins.
