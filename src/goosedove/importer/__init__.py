"""The importer, import-cleared-futures.md: what turns an API's answers into trade rows for the
sheet, apart from the pricing library, which never imports it, and from the seam, which it never
imports. It knows the workbook only through what the host hands it, the IDs the tables already
hold, and hands back what the host should fetch and, later, the rows to insert; the economics of a
row stay _CreateTrades's to check. Three modules: `fetch`, the filter request; `walk`, the
filter's answer read into IDs and walked against the workbook's; `run`, one run of the first
slice and the line it writes."""
