"""The market: what the pricing will take, prepared once and reached by handle. Its history is
an index's calendar bound to the settle fixed on each of its past business days, the first
object that reads the market data against the calendar; the market itself is the history
combined with the current futures prices, one quote per contract from the valuation day's
prompt through the last, so that every business day of the calendar has a price, the fixing
where the day has fixed and the prompt contract's quote where it has not.

Two frozen records, each with one builder that checks its meaning once. Nothing here imports
the Excel bridge; docs/library/market/ holds a page per worksheet function.
"""
