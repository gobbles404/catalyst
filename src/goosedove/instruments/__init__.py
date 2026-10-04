"""The instrument catalog: the library's own definitions of what a trade may be, each a name, a
description and its fields, every field with the words a person needs to fill a template or a
ticket under it, its name, what it means, whether and when it is required, its type, its
choices and its rule. The desk selects a definition and inspects it; it does not author one.
Today the catalog holds `future`. Built in #NN as ticket I2 of the trade-valuation pipeline;
_ListInstruments and _ShowInstrument read it, and template and trade creation will read the
same records. docs/library/instruments/ holds a page per function.
"""
