"""The market definitions: what an index is, as opposed to the globals every calculation starts
from; today an expiry schedule, the contract months of one index and their expiry dates.

Each is a small frozen record and one builder that checks its meaning once. Nothing here
imports the Excel bridge; docs/library/market-definitions/ holds a page per worksheet function.
"""
