"""The index definitions: the pieces one index is defined by, as opposed to the globals every
calculation starts from; today an expiry schedule, the contract months of one index and their
expiry dates, a holiday calendar, the days one market is closed, the index conventions, the
units one index is quoted, settled and measured in, and contract specs, the name, lot size and
fees per lot of each contract an index trades as. A creator that ties them into one index
definition is the owner's next, not yet specified.

Each is a small frozen record and one builder that checks its meaning once. Nothing here
imports the Excel bridge; docs/library/index-definitions/ holds a page per worksheet function.
"""
