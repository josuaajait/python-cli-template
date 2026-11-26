"""Terminal presentation and complete machine-readable command results."""
from contextvars import ContextVar, Token
import itertools
import json
import os
from pathlib import Path
import re
import shutil
import sys
import threading
from typing import Any, TextIO
import unicodedata

from rich import box
from rich.console import Console as RichConsole
from rich.console import RenderableType
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .archives import DEFAULT_APP_ID, DEFAULT_LOG_ENV, log_directory, save_result
from .status import FAILED, GOOD, WARN
from .summary import preview


_active: ContextVar['Console | None'] = ContextVar('cli_console', default=None)
_escapes = re.compile(r'\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b\[[0-?]*[ -/]*[@-~]|\x1b[@-_]')
_controls = re.compile(r'[\x00-\x08\x0b-\x1f\x7f-\x9f]')


def current_console() -> 'Console | None':
    return _active.get()


def progress(message: str) -> None:
    console = current_console()
    if console is not None:
        console.progress(message)


def notice(message: str, level: str = 'INFO') -> None:
    console = current_console()
    if console is not None:
        console.notice(message, level)


def _clean(value: object) -> str:
    return _controls.sub('', _escapes.sub('', str(value))).replace('\t', '    ')


def _terminal_text(value: object, stream: TextIO) -> str:
    encoding = getattr(stream, 'encoding', None) or 'utf-8'
    return _clean(value).encode(encoding, errors='replace').decode(encoding)


def _cell_width(text: str) -> int:
    return sum(0 if unicodedata.combining(char) or char in '\u200d\ufe0f'
               else 2 if unicodedata.east_asian_width(char) in ('W', 'F') else 1
               for char in text)


def _wrap_cells(text: str, width: int) -> list[str]:
    """Wrap plain text by terminal cells, keeping wide glyphs together."""
    lines: list[str] = []
    for paragraph in text.split('\n'):
        if not paragraph:
            lines.append('')
        while paragraph:
            used = end = 0
            for char in paragraph:
                char_width = _cell_width(char)
                if used + char_width > width:
                    break
                used += char_width
                end += 1
            end = max(1, end)
            if end < len(paragraph):
                space = paragraph.rfind(' ', 0, end + 1)
                if space > 0:
                    end = space
            lines.append(paragraph[:end].rstrip())
            paragraph = paragraph[end:].lstrip()
    return lines


def _label(key: object) -> str:
    return str(key).replace('_', ' ').capitalize()


def _value(value: object) -> str:
    if value is None:
        return 'N/A'
    if isinstance(value, bool):
        return 'yes' if value else 'no'
    return _clean(value)


class Console:
    def __init__(self, *, title: str = 'PYTHON CLI', description: str = 'A reusable Python CLI starter',
                 mode: str = 'auto', no_color: bool = False,
                 app_id: str = DEFAULT_APP_ID, log_env: str = DEFAULT_LOG_ENV) -> None:
        self.title, self.description = title, description
        self.app_id, self.log_env = app_id, log_env
        self.output: TextIO = sys.stdout
        self.errors: TextIO = sys.stderr
        self.essential: tuple[str, ...] = ()
        self.log_dir: str | None = None
        self._summarized = False
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._token: Token[Console | None] | None = None
        self._lock = threading.RLock()
        self.configure(mode, no_color)

    @property
    def archive_root(self) -> Path:
        return log_directory(self.log_dir, app_id=self.app_id, env=self.log_env)

    def configure(self, mode: str = 'auto', no_color: bool = False) -> None:
        self.pretty = mode == 'pretty' or (mode == 'auto' and self.output.isatty())
        self.no_color = no_color or 'NO_COLOR' in os.environ or os.environ.get('TERM') == 'dumb'

    @property
    def width(self) -> int:
        return max(16, min(120, shutil.get_terminal_size((88, 24)).columns - 1))

    def _color_enabled(self, stream: TextIO) -> bool:
        # Legacy Windows consoles without ANSI support get the same plain layout.
        supported = os.name != 'nt' or any(os.environ.get(key) for key in ('WT_SESSION', 'ANSICON', 'TERM'))
        return self.pretty and not self.no_color and stream.isatty() and supported

    def _style(self, text: str, code: str, stream: TextIO) -> str:
        if self._color_enabled(stream):
            return f'\x1b[{code}m{text}\x1b[0m'
        return text

    def _print(self, text: object = '', *, stream: TextIO | None = None, code: str | None = None) -> None:
        stream = stream or self.output
        # ASCII borders and replacement for unsupported characters keep old Windows
        # code pages usable. No escaping/sanitizing is applied to JSON data.
        line = _terminal_text(text, stream)
        if code:
            line = self._style(line, code, stream)
        with self._lock:
            print(line, file=stream, flush=True)

    def _rich(self, renderable: RenderableType) -> None:
        color = self._color_enabled(self.output)
        renderer = RichConsole(file=self.output, width=self.width, color_system='standard' if color else None,
                               force_terminal=color, legacy_windows=False, highlight=False, markup=False)
        renderer.print(renderable)

    def header(self, command: str) -> None:
        if self.pretty:
            title = Text('  ', style='on cyan')
            title.append(' ' + _terminal_text(self.title, self.output), style='bold cyan')
            title.append('  /  ' + _terminal_text(command, self.output))
            title.append('\n   ' + _terminal_text(self.description, self.output), style='dim')
            self._rich(title)
            self._print('')

    def keep(self, *fields: str) -> None:
        """Show these top-level fields first and render their entire subtrees."""
        self.essential = tuple(dict.fromkeys((*self.essential, *fields)))

    def result(self, value: Any, *, exit_code: int = 0, archive: bool = True,
               trace: str | None = None, debug: bool = False) -> None:
        self.stop()
        status: object = value.get('status') if isinstance(value, dict) else None
        if status is None and isinstance(value, dict):
            if 'ready' in value:
                status = 'READY' if value['ready'] else 'NOT READY'
            elif 'valid' in value:
                status = 'VALID' if value['valid'] else 'INVALID'
        status = str(status or 'RESULT')
        failed = exit_code not in (0, 130) or status.upper() in FAILED
        self._summarized = False
        if self.pretty:
            color = 'green' if status in GOOD else 'red' if failed else 'yellow' if status in WARN else 'cyan'
            heading = Text(_terminal_text(status, self.output), style='bold ' + color)
            body: Any = value
            if isinstance(value, dict):
                body = {key: value[key] for key in (*self.essential, *value) if key in value and key != 'status'}
                if all(type(body.get(key)) is int for key in ('succeeded', 'failed')):
                    counts = f"   {body.pop('succeeded')} succeeded  /  {body.pop('failed')} failed"
                    heading.append(_terminal_text(counts, self.output))
            self._rich(heading)
            if isinstance(body, dict):
                for key in self.essential:
                    if key in body:
                        self._section(_label(key))
                        self._render(body.pop(key), full=True)
                if failed and ('error' in body or 'message' in body):
                    error_key = 'error' if 'error' in body else 'message'
                    error = Text(_terminal_text(_value(body.pop(error_key)), self.output))
                    if 'location' in body:
                        error.append('\n' + _terminal_text(body.pop('location'), self.output), style='dim')
                    self._rich(Panel(error, box=box.ASCII, border_style='red', expand=False))
            if body or not isinstance(body, dict):
                self._render(body)
        else:
            print(json.dumps(value, ensure_ascii=True, indent=2), file=self.output)

        if archive and (self._summarized or failed):
            try:
                path = save_result(self.archive_root, value, trace)
            except (OSError, RuntimeError, ValueError) as error:
                self._print(f'WARNING: Cannot save archive: {error}', stream=self.errors)
                self._print(json.dumps(value, ensure_ascii=True, indent=2), stream=self.errors)
                if trace:
                    self._print(trace, stream=self.errors)
                    debug = False
            else:
                self._print(f'Archive: {path}', stream=self.output if self.pretty else self.errors)
        elif self._summarized:
            self._print('Full result: use --json.')
        if debug and trace:
            self._print(trace, stream=self.errors)

    def _section(self, title: str) -> None:
        self._print('')
        for line in _wrap_cells(_terminal_text(title, self.output), self.width - 2):
            self._print(' ' + line, code='1;36')

    def _render(self, value: Any, *, full: bool = False) -> None:
        if isinstance(value, dict):
            if not value:
                self._print(' (empty)')
            scalars = [[_label(key), _value(item)] for key, item in value.items()
                       if not isinstance(item, (dict, list))]
            if scalars:
                self._table(['Field', 'Value'], scalars)
            for key, item in value.items():
                if not isinstance(item, (dict, list)):
                    continue
                self._section(_label(key))
                self._render(item, full=full)
        elif isinstance(value, list):
            if not full:
                selection = preview(value)
                if selection.omitted or selection.groups:
                    self._summarized = True
                    self._print(f' {len(value)} total; {selection.omitted} rows omitted from preview.')
                    if selection.groups:
                        for group in selection.groups:
                            self._section(f"{group['count']} failed: {group['reason']}")
                            self._render(group['example'])
                        return
                    value = selection.rows
            if not value:
                self._print(' (empty)')
            elif all(isinstance(item, dict) and all(not isinstance(v, (dict, list)) for v in item.values())
                     for item in value):
                keys = list(dict.fromkeys(key for item in value for key in item))
                self._table([_label(key) for key in keys],
                            [[_value(item.get(key)) for key in keys] for item in value])
            else:
                for index, item in enumerate(value, 1):
                    if isinstance(item, (dict, list)):
                        self._section(str(index))
                        self._render(item, full=full)
                    else:
                        for line in _wrap_cells(_terminal_text(_value(item), self.output), self.width - 4):
                            self._print(' - ' + line)
        else:
            self._print(' ' + _value(value))

    def _table(self, headings: list[str], rows: list[list[str]]) -> None:
        if not headings:
            self._print(' (empty)')
            return
        cells = [[_terminal_text(cell, self.output) for cell in row] for row in [headings, *rows]]
        # A vertical record layout is more readable than one-character columns.
        if len(headings) * 9 + 1 > self.width:
            for index, row in enumerate(cells[1:], 1):
                self._print(f' [{index}]', code='36')
                for heading, cell in zip(cells[0], row, strict=True):
                    for line in _wrap_cells(f'{heading}: {cell}', self.width - 2):
                        self._print(' ' + line)
            return
        wide = any(_cell_width(char) == 2 for row in cells for cell in row for char in cell)
        can_draw = self._color_enabled(self.output) and _terminal_text('╭', self.output) == '╭'
        table = Table(box=box.ROUNDED if can_draw else box.ASCII, border_style='dim cyan', header_style='bold cyan',
                      padding=(0, 1), safe_box=False)
        for heading in cells[0]:
            table.add_column(Text(heading), overflow='fold', min_width=2 if wide else 1)
        for row in cells[1:]:
            table.add_row(*(Text(cell) for cell in row))
        self._rich(table)

    def notice(self, message: object, level: str = 'INFO') -> None:
        self.stop()
        if not self.pretty:
            return
        color = '31' if level == 'ERROR' else '33' if level == 'WARN' else '32' if level == 'OK' else '36'
        for index, line in enumerate(_clean(message).splitlines()):
            self._print(f' [{level}] {line}' if index == 0 else ' ' + line,
                        stream=self.errors, code=color)

    def message(self, message: str) -> None:
        """Interactive messages are retained even in machine-output mode."""
        if self.pretty:
            self.notice(message)
        else:
            self.stop()
            self._print(message, stream=self.errors)

    def read(self, prompt: object) -> str:
        self.stop()
        with self._lock:
            print(self._style(_terminal_text(' > ' + str(prompt), self.errors), '1;36', self.errors),
                  end='', file=self.errors, flush=True)
        return input()

    def error(self, message: str) -> None:
        if self.pretty:
            self.notice(message, 'ERROR')
        else:
            self.stop()
            print(message, file=self.errors)

    def progress(self, message: str) -> None:
        self.notice(message, 'WORKING')
        if not self.pretty or not self.errors.isatty() or os.environ.get('TERM') == 'dumb':
            return
        self._stop.clear()

        def animate() -> None:
            for frame in itertools.cycle('|/-\\'):
                if self._stop.wait(0.12):
                    break
                line = _wrap_cells(_terminal_text(f' {frame} {message}', self.errors), self.width)[0]
                with self._lock:
                    print('\r' + line + ' ' * (self.width - _cell_width(line)), end='', file=self.errors, flush=True)
            with self._lock:
                print('\r' + ' ' * self.width + '\r', end='', file=self.errors, flush=True)

        self._thread = threading.Thread(target=animate, name='cli-spinner', daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._thread is not None:
            self._stop.set()
            self._thread.join()
            self._thread = None

    def __enter__(self) -> 'Console':
        self._token = _active.set(self)
        return self

    def __exit__(self, *exc: object) -> None:
        self.stop()
        if self._token is not None:
            _active.reset(self._token)
            self._token = None
