"""The market data: the prices of one index, as opposed to the globals every calculation starts
from and the index definitions that say what an index is; today its fixings, the settle on each
day it fixed or the price for each contract month on the day it was published, for an index
published once a month, and its futures prices as a vendor feeds them, one column snapped as a
vector each time the sheet recalculates. The market history, goosedove.market, binds the futures
fixings to the index's calendar, and the market combines that history with a price vector;
the functions that bind the fixings to an index definition and price and risk instruments off
the market are not built.

Each is a small frozen record and one builder that checks its meaning once. Nothing here
imports the Excel bridge; docs/library/market-data/ holds a page per worksheet function.
"""
