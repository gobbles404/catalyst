"""What Excel sees: every module that registers worksheet functions, imported here once.

The host imports the bridge, which imports this package first, so the function list
is complete by the time the host asks for it. A new module of worksheet functions is
added here and nowhere else. The probes are not among them: they are test support, the
`catalyst_probes` package outside `src`, registered only where a test, a measurement
runner or a host's config asks for them.
"""

from catalyst.excel import (
    bridge,
    calendar,
    cashflows,
    globals,
    index_definitions,
    instruments,
    market,
    market_data,
    quoting,
    trades,
    utilities,
)

__all__ = [
    "bridge",
    "calendar",
    "cashflows",
    "globals",
    "index_definitions",
    "instruments",
    "market",
    "market_data",
    "quoting",
    "trades",
    "utilities",
]
