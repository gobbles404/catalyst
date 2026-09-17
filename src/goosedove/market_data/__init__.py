"""The market data: the prices of one index, as opposed to the globals every calculation starts
from and the index definitions that say what an index is; today a futures curve, the price of
each contract of one index on one day. The functions that bind a curve to an index and price
and risk instruments off it are not built.

Each is a small frozen record and one builder that checks its meaning once. Nothing here
imports the Excel bridge; docs/library/market-data/ holds a page per worksheet function.
"""
