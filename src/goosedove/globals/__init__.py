"""The globals: the shared objects every calculation starts from, a valuation date and a curve.

Each is a small frozen record and one builder that checks its meaning once; beside them, the
interpolation that fills the days between a curve's anchors. Nothing here imports the Excel
bridge; docs/library/globals/ holds a page per worksheet function.
"""
