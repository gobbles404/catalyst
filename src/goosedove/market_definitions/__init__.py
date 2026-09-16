"""The market definitions: what an index or a market is, as opposed to the globals every
calculation starts from; today an expiry schedule, the contract months of one index and their
expiry dates, and a holiday calendar, the days one market is closed.

Each is a small frozen record and one builder that checks its meaning once. Nothing here
imports the Excel bridge; docs/library/market-definitions/ holds a page per worksheet function.
"""
