"""The valuation: from what the trades require of the market and the prices of what they read
to the amounts, one per component in the settlement currency, and what a move in each mark
does to them.

Three records and one module of arithmetic, each one job. The terms are what the trades
require: one row per component per observation it reads, with the coefficient that multiplies
that observation's price, and one fixed leg per component, the sheet's exploded view, made once
when the trades are encoded and holding no price. The binding is where each observation's price
comes from for one fixing state, its print where it has fixed and the contract whose mark prices
it where it has not, holding no mark; it refuses a fixed observation without a print, and a
tick brings only the marks. The kernel is the arithmetic between them: the amounts, the
compressed view of the terms under one binding, per component its fixed leg, the printed part
of its floating leg and one coefficient per mark, which is the sensitivity table and prices a
new vector of marks in one multiply, and the dense view for the eye. Nothing here imports the
Excel bridge; docs/library/valuation/kernel.md is the page.
"""
