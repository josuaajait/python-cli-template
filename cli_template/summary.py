
"""Choose representative rows without mutating the machine-readable payload."""
from dataclasses import dataclass

from .status import FAILED


PREVIEW_ROWS = 8


@dataclass
class Preview:
    rows: list
    omitted: int
    groups: list


def failure_reason(row):
    if not isinstance(row, dict):
        return None
    reason = row.get('reason') or row.get('error')
    failed = (str(row.get('status', '')).upper() in FAILED
              or row.get('ok') is False or row.get('valid') is False or bool(row.get('error')))
    if failed:
        return str(reason or row.get('message') or row.get('detail') or 'Cause unavailable')
    return None


def preview(rows):
    if len(rows) <= PREVIEW_ROWS:
        return Preview(rows, 0, [])
    failures = []
    groups = {}
    for row in rows:
        cause = failure_reason(row)
        if cause is not None:
            failures.append(row)
            if cause in groups:
                groups[cause]['count'] += 1
            else:
                groups[cause] = {'reason': cause, 'count': 1, 'example': row}
    if len(failures) > PREVIEW_ROWS:
        return Preview([], len(rows) - len(groups), list(groups.values()))
    chosen = failures or rows[:PREVIEW_ROWS]
    return Preview(chosen, len(rows) - len(chosen), [])
