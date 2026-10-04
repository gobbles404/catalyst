"""What Excel sees: every module that registers worksheet functions, imported here once.

The host imports the bridge, which imports this package first, so the function list
is complete by the time the host asks for it. A new module of worksheet functions is
added here and nowhere else.
"""

from goosedove.excel import (
    bridge,
    calendar,
    globals,
    index_definitions,
    instruments,
    market,
    market_data,
    probes,
    trades,
    utilities,
)

__all__ = [
    "bridge",
    "calendar",
    "globals",
    "index_definitions",
    "instruments",
    "market",
    "market_data",
    "probes",
    "trades",
    "utilities",
]
