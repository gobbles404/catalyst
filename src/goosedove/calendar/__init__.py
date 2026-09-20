"""The calendar: every day of one index from the day after its first contract expires to the
day its last expires, with the contract prompt on each day, whether the market is open and
whether the day is before the valuation date, for daily or for monthly fixings as the caller
says. It is built from three objects the sheet already holds, the valuation date, the expiry
schedule and the holiday calendar, and holds no price:
the market history, goosedove.market, fills its past business days from the fixings and keeps
it as it is; the pricing that will run along it is not built.

One frozen record and one builder that checks its meaning once. Nothing here imports the Excel
bridge; docs/library/calendar/calendar.md is the page.
"""
