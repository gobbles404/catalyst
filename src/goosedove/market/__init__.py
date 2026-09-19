"""The market: what the pricing will take, prepared once and reached by handle. Today its
history, an index's calendar bound to the settle fixed on each of its past business days, the
first object that reads the market data against the calendar; the market itself, the history
combined with a vector of prices for the days to come, is not built.

One frozen record and one builder that checks its meaning once. Nothing here imports the Excel
bridge; docs/library/market/market-history.md is the page.
"""
