"""The index definitions: the pieces one index is defined by, as opposed to the globals every
calculation starts from; today a futures schedule, the contract months of one index and their
expiry dates, a holiday calendar, the days one market is closed, the index conventions, the
units one index is quoted, settled and measured in, and contract specifications, the name, lot
size and fees per lot of each contract an index trades as; and, since #NN, the index itself,
which binds a name to its schedule, conventions, specifications and, for a futures index, holiday
calendar, with the kinds and the holiday rule the index and the calendar share.

Each is a small frozen record and one builder that checks its meaning once. Nothing here
imports the Excel bridge; docs/library/index-definitions/ holds a page per worksheet function.
"""
