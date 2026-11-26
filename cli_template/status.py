"""Status vocabulary shared by row summaries and terminal rendering."""

GOOD = frozenset({'SUCCESS', 'READY', 'PASSED', 'VALID', 'COMPLETE'})
FAILED = frozenset({'ERROR', 'INVALID', 'FAILED', 'NOT READY'})
WARN = frozenset({'WARNING', 'CANCELLED', 'SKIPPED'})
