"""The active detector pack.

**One list, imported everywhere.** The hook, the PreToolUse hook, the HTTP gateway, the
app-server client and the Part A adapter each used to build their own
`list(EXAMPLE_DETECTORS)`. Five copies of "what do we detect" is five answers, and the one
that mattered would be whichever path a request happened to take -- the same failure that
let a duplicated finding-conversion drift within a day.

Adding a detector means adding it here, once.
"""

from .example import EXAMPLE_DETECTORS
from .india_id import INDIA_ID_DETECTORS

#: Everything that ships. Order is not significant: the scanner builds one automaton and
#: one alternation over the whole pack.
ALL_DETECTORS = tuple(EXAMPLE_DETECTORS) + tuple(INDIA_ID_DETECTORS)

__all__ = ["ALL_DETECTORS", "EXAMPLE_DETECTORS", "INDIA_ID_DETECTORS"]
