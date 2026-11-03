"""The market: what the pricing will take, prepared once and reached by handle. Its history is
an index's calendar bound to the price fixed on each of its periods that has fixed, from the
fixings of the calendar's market, futures, Gas Daily or IFERC, the first object that reads the
market data against the calendar; the market itself is the history combined with the quotes of
the periods still to come, one quote per contract from the first unfixed period's contract on,
through the schedule's last or stopping before it, so that every priced period the quotes
cover has a price, the fixing where the period has fixed and its contract's quote where it has
not, and a contract past the last one quoted is refused by name.

Two frozen records, each with one builder that checks its meaning once. Nothing here imports
the Excel bridge; docs/library/market/ holds a page per worksheet function.
"""
