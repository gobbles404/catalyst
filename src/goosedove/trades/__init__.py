"""The trades: a batch of one or many trade occurrences on one index, carried through the four
steps of the trade-valuation pipeline. The resolved terms say which deals were struck, under
which definitions; the encoding turns them into static arrays and names the market inputs they
consume, with no history or price in sight; the preparation applies one market history to the
encoding, folding the contracts that have fixed and summing the exposure to each contract still
live; and the evaluation prices the prepared batch against one market, publishing mark, cash and
risk for the batch as a whole. One occurrence takes the same path as a thousand, and every
occurrence counts, a duplicate twice.

Four frozen records, each with one builder that checks its meaning once, every array owned and
read-only. Built first for the NG example of docs/engineering-tickets/trade-valuation-pipeline/,
as ticket I1 of its README; nothing here imports the Excel bridge, and no worksheet function
reaches it yet, so the resolved terms are supplied in Python until _CreateTrades resolves them
from a template and a ticket. docs/library/trades/kernel.md is the page.
"""
