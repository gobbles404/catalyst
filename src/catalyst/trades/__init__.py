"""The trades: a batch of one or many trade occurrences on one index, carried through the four
steps of the trade-valuation pipeline. The resolved terms say which deals were struck, under
which definitions, and the observations which days' settles price each component; the encoding
turns them into static arrays on dated slots, an observation day within a payment group with the
contract pricing that day as its reference, with no history or price in sight; the preparation
applies one market history to the encoding, fixing the slots whose day has passed and summing
the live exposure to each reference; and the evaluation prices the prepared batch against one
market, publishing mark, cash and risk for the batch as a whole. One occurrence takes the same
path as a thousand, and every occurrence counts, a duplicate twice.

Five frozen records, each with one builder that checks its meaning once, every array owned and
read-only. Built first for the NG example of docs/engineering-tickets/trade-valuation-pipeline/,
as ticket I1 of its README, and reached from the sheet since ticket I4: the template and the
resolution modules make the terms from a template and a ticket, and _CreateTrades publishes
the batch. Nothing here imports the Excel bridge. docs/library/trades/kernel.md,
trade-template.md and create-trades.md are the pages.
"""
