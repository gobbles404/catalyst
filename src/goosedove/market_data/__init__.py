"""The market data: the prices of one index, as opposed to the globals every calculation starts
from and the index definitions that say what an index is; today a futures curve, the price of
each contract of one index on one day, and its fixings, the settle on each day it fixed or the
price for each contract month on the day it was published, for an index published once a
month. The functions that bind them to an index and price and risk instruments off them are
not built.

Each is a small frozen record and one builder that checks its meaning once. Nothing here
imports the Excel bridge; docs/library/market-data/ holds a page per worksheet function.
"""
