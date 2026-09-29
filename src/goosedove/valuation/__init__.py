"""The valuation: from what the trades require of the market and the prices of what they read
to the amounts, one per component in the settlement currency, and what a move in each mark
does to them.

Three records and one module of arithmetic, each one job. The terms are what the trades
require: one row per component per observation it reads, with the coefficient that multiplies
that observation's price, and one constant per component, the sheet's exploded view, made once
when the trades are encoded and holding no price. The binding is one price per observation for
one valuation, the print where the observation has fixed and its mark where it has not, and it
refuses a fixed observation without a print. The kernel is the arithmetic between them: the
amounts, the compressed view of the terms under one binding, one coefficient per component per
mark plus a constant, which is the sensitivity table and prices a new vector of marks in one
multiply, and the dense view for the eye. Nothing here imports the Excel bridge;
docs/library/valuation/kernel.md is the page.
"""
