"""The calendar: every day of one index from the day after its first contract expires to the
day its last expires, with the contract prompt on each day, whether the market is open and
whether the day is before the valuation date. It is built from three objects the sheet already
holds, the valuation date, the expiry schedule and the holiday calendar, and holds no price:
the pricing that will run along it, and the fixings that will fill it, are not built.

One frozen record and one builder that checks its meaning once. Nothing here imports the Excel
bridge; docs/library/calendar/calendar.md is the page.
"""
