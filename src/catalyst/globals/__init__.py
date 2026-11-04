"""The globals: the shared objects every calculation starts from, a valuation date, a curve and
the unit definitions.

Each is a small frozen record and one builder that checks its meaning once; beside them, the
interpolation that fills the days between a curve's anchors. Nothing here imports the Excel
bridge; docs/library/globals/ holds a page per function, the unit conversions having no
worksheet surface.
"""
