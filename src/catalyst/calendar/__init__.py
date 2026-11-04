"""The calendar: the periods one index prices, from any of its three schedules, each with the
contract it belongs to, whether it prices and whether it is on the fixed side of the valuation
date. It is built from the valuation date, the schedule and, for a futures schedule, the
holiday calendar the sheet already holds, and holds no price: the market history,
catalyst.market, fills its fixed periods from the fixings and keeps it as it is; the pricing
that will run along it is not built.

One frozen record and one builder that checks its meaning once. Nothing here imports the Excel
bridge; docs/library/calendar/calendar.md is the page.
"""
