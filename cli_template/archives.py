"""Per-user, explicitly managed archives of complete command results."""
from collections.abc import Callable
from dataclasses import dataclass
import json
import os
from pathlib import Path
from pprint import pformat
import re
import stat
import sys
from typing import Any
from uuid import uuid4


_RUN_NAME = re.compile(r'run-[0-9a-f]{32}')
_FILES = ('result.json', 'result.log')
DEFAULT_APP_ID = 'python-cli-template'
DEFAULT_LOG_ENV = 'PYTHON_CLI_LOG_DIR'


def log_directory(override: str | os.PathLike[str] | None = None, *,
                  app_id: str = DEFAULT_APP_ID, env: str = DEFAULT_LOG_ENV) -> Path:
    if override or os.environ.get(env):
        return Path(override or os.environ[env]).expanduser().absolute()
    if os.name == 'nt':
        base = Path(os.environ['LOCALAPPDATA']) if 'LOCALAPPDATA' in os.environ else Path.home() / 'AppData/Local'
    elif sys.platform == 'darwin':
        base = Path.home() / 'Library/Logs'
    else:
        base = Path(os.environ['XDG_STATE_HOME']) if 'XDG_STATE_HOME' in os.environ else Path.home() / '.local/state'
    return base / app_id / 'logs'


def save_result(root: Path, value: Any, trace: str | None) -> Path:
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    run_id = uuid4().hex
    staging = root / f'.pending-{run_id}'
    destination = root / f'run-{run_id}'
    staging.mkdir(mode=0o700)
    try:
        with (staging / 'result.json').open('x', encoding='utf-8') as stream:
            json.dump(value, stream, ensure_ascii=True, indent=2)
            stream.write('\n')
        with (staging / 'result.log').open('x', encoding='utf-8', errors='backslashreplace') as stream:
            stream.write(pformat(value, sort_dicts=False, width=100) + '\n')
            if trace:
                stream.write('\n' + trace)
        staging.rename(destination)
    finally:
        if staging.exists():
            for name in _FILES:
                (staging / name).unlink(missing_ok=True)
            staging.rmdir()
    return destination


@dataclass(frozen=True)
class ArchiveSnapshot:
    directory_id: tuple[int, int]
    files: tuple[tuple[int, int, int, int], ...]
    size: int

    @property
    def saved_ns(self) -> int:
        """When result.json was written, in nanoseconds since the epoch."""
        return self.files[0][3]


def _regular(info: os.stat_result, kind: Callable[[int], bool]) -> bool:
    return kind(info.st_mode) and not (
        getattr(info, 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
    )


def _snapshot(path: Path) -> ArchiveSnapshot | None:
    info = path.lstat()
    if not _regular(info, stat.S_ISDIR) or {p.name for p in path.iterdir()} != set(_FILES):
        return None
    files = [(path / name).lstat() for name in _FILES]
    if not all(_regular(file, stat.S_ISREG) for file in files):
        return None
    return ArchiveSnapshot((info.st_dev, info.st_ino),
                           tuple((f.st_dev, f.st_ino, f.st_size, f.st_mtime_ns) for f in files),
                           sum(f.st_size for f in files))


def list_archives(root: Path) -> dict[Path, ArchiveSnapshot]:
    entries: dict[Path, ArchiveSnapshot] = {}
    if root.exists():
        for path in root.iterdir():
            if _RUN_NAME.fullmatch(path.name):
                try:
                    snapshot = _snapshot(path)
                except FileNotFoundError:
                    continue
                if snapshot is not None:
                    entries[path] = snapshot
    return entries


def run_id(path: Path) -> str:
    return path.name.removeprefix('run-')


def find_archive(entries: dict[Path, ArchiveSnapshot], prefix: str) -> Path:
    """The single archive whose run ID starts with `prefix` (a leading 'run-' is accepted)."""
    wanted = prefix.strip().lower().removeprefix('run-')
    if not re.fullmatch(r'[0-9a-f]{1,32}', wanted):
        raise LookupError(f'Run ID must be 1-32 hexadecimal characters: {prefix}')
    matches = [path for path in entries if run_id(path).startswith(wanted)]
    if not matches:
        raise LookupError(f'No saved run matches {prefix}.')
    if len(matches) > 1:
        raise LookupError(f'{len(matches)} saved runs match {prefix}; use more characters.')
    return matches[0]


def read_result(path: Path) -> Any:
    with (path / 'result.json').open(encoding='utf-8') as stream:
        return json.load(stream)


def clean_archives(entries: dict[Path, ArchiveSnapshot]) -> int:
    removed = 0
    for path, expected in entries.items():
        claimed = path.with_name('.cleaning-' + uuid4().hex)
        try:
            path.rename(claimed)
        except FileNotFoundError:
            continue
        try:
            if _snapshot(claimed) != expected:
                continue
            for name in _FILES:
                (claimed / name).unlink()
            claimed.rmdir()
            removed += 1
        finally:
            if os.path.lexists(claimed) and not os.path.lexists(path):
                claimed.rename(path)
    return removed
