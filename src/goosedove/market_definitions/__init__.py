"""The market definitions: what an index, a market or a contract is, as opposed to the globals
every calculation starts from; today an expiry schedule, the contract months of one index and
their expiry dates, a holiday calendar, the days one market is closed, the market conventions,
the units one index is quoted, settled and measured in, and a contract spec, the name, lot
size and fees per lot of one contract.

Each is a small frozen record and one builder that checks its meaning once. Nothing here
imports the Excel bridge; docs/library/market-definitions/ holds a page per worksheet function.
"""
