"""PTerm-inspired presentation using only Python's standard library.

Presentation stays separate from application logic and command exit codes.
"""
from contextvars import ContextVar
import itertools
import json
import os
import re
import shutil
import sys
import threading
import unicodedata


_active = ContextVar('cli_console', default=None)
_escapes = re.compile(r'\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b\[[0-?]*[ -/]*[@-~]|\x1b[@-_]')
_controls = re.compile(r'[\x00-\x08\x0b-\x1f\x7f-\x9f]')
_good = {'SUCCESS', 'READY', 'PASSED', 'VALID', 'COMPLETE'}
_bad = {'ERROR', 'INVALID', 'FAILED'}
_warn = {'WARNING', 'CANCELLED', 'SKIPPED', 'NOT READY'}


def current_console():
    return _active.get()


def progress(message):
    console = current_console()
    if console is not None:
        console.progress(message)


def notice(message, level='INFO'):
    console = current_console()
    if console is not None:
        console.notice(message, level)


def _clean(value):
    return _controls.sub('', _escapes.sub('', str(value))).replace('\t', '    ')


def _terminal_text(value, stream):
    encoding = getattr(stream, 'encoding', None) or 'utf-8'
    return _clean(value).encode(encoding, errors='replace').decode(encoding)


def _cell_width(text):
    return sum(0 if unicodedata.combining(char) or char in '\u200d\ufe0f'
               else 2 if unicodedata.east_asian_width(char) in ('W', 'F') else 1
               for char in text)


def _wrap_cells(text, width):
    """Wrap plain text by terminal cells, keeping wide glyphs together."""
    lines = []
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


def _label(key):
    return str(key).replace('_', ' ').capitalize()


def _value(value):
    if value is None:
        return 'N/A'
    if isinstance(value, bool):
        return 'yes' if value else 'no'
    return _clean(value)


class Console:
    def __init__(self, *, title='PYTHON CLI', description='A reusable Python CLI starter',
                 mode='auto', no_color=False):
        self.title, self.description = title, description
        self.output, self.errors = sys.stdout, sys.stderr
        self._stop = threading.Event()
        self._thread = None
        self._lock = threading.RLock()
        self.configure(mode, no_color)

    def configure(self, mode='auto', no_color=False):
        self.pretty = mode == 'pretty' or (mode == 'auto' and self.output.isatty())
        self.no_color = no_color or 'NO_COLOR' in os.environ or os.environ.get('TERM') == 'dumb'

    @property
    def width(self):
        return max(16, min(120, shutil.get_terminal_size((88, 24)).columns - 1))

    def _style(self, text, code, stream):
        # Legacy Windows consoles without ANSI support get the same plain layout.
        supported = os.name != 'nt' or any(os.environ.get(key) for key in ('WT_SESSION', 'ANSICON', 'TERM'))
        if self.pretty and not self.no_color and stream.isatty() and supported:
            return f'\x1b[{code}m{text}\x1b[0m'
        return text

    def _print(self, text='', *, stream=None, code=None):
        stream = stream or self.output
        # ASCII borders and replacement for unsupported characters keep old Windows
        # code pages usable. No escaping/sanitizing is applied to JSON data.
        text = _terminal_text(text, stream)
        if code:
            text = self._style(text, code, stream)
        with self._lock:
            print(text, file=stream, flush=True)

    def header(self, command):
        if not self.pretty:
            return
        self._print('')
        for line in _wrap_cells(_terminal_text(self.title, self.output), self.width - 2):
            self._print(' ' + line + ' ', code='1;97;44')
        for line in _wrap_cells(_terminal_text(f'{command} / {self.description}', self.output), self.width - 2):
            self._print(' ' + line, code='36')
        self._print(' ' + '-' * (self.width - 2), code='36')

    def result(self, value):
        self.stop()
        if not self.pretty:
            # JSON escapes preserve Unicode values even on legacy code pages.
            print(json.dumps(value, ensure_ascii=True, indent=2), file=self.output)
            return
        status = value.get('status') if isinstance(value, dict) else None
        if status is None and isinstance(value, dict):
            if 'ready' in value:
                status = 'READY' if value['ready'] else 'NOT READY'
            elif 'valid' in value:
                status = 'VALID' if value['valid'] else 'INVALID'
        self._print('')
        if status is not None:
            status = str(status)
        code = '32' if status in _good else '31' if status in _bad else '33' if status in _warn else '36'
        self._print(f' [ {status or "RESULT"} ]', code='1;' + code)
        self._render(value)
        self._print('')

    def _section(self, title):
        self._print('')
        for line in _wrap_cells(_terminal_text(title, self.output), self.width - 2):
            self._print(' ' + line, code='1;36')

    def _render(self, value):
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
                self._render(item)
        elif isinstance(value, list):
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
                        self._render(item)
                    else:
                        for line in _wrap_cells(_terminal_text(_value(item), self.output), self.width - 4):
                            self._print(' - ' + line)
        else:
            self._print(' ' + _value(value))

    def _table(self, headings, rows):
        if not headings:
            self._print(' (empty)')
            return
        cells = [[_terminal_text(cell, self.output) for cell in row] for row in [headings, *rows]]
        # A vertical record layout is more readable than one-character columns.
        if len(headings) * 9 + 1 > self.width:
            for index, row in enumerate(cells[1:], 1):
                self._print(f' [{index}]', code='36')
                for heading, cell in zip(cells[0], row):
                    for line in _wrap_cells(f'{heading}: {cell}', self.width - 2):
                        self._print(' ' + line)
            return
        minima = [2 if any(_cell_width(char) == 2 for row in cells for char in row[i]) else 1
                  for i in range(len(headings))]
        widths = [max(minima[i], max(_cell_width(line) for row in cells for line in row[i].split('\n')))
                  for i in range(len(headings))]
        available = self.width - (3 * len(widths) + 1)
        while sum(widths) > available:
            widest = max((i for i in range(len(widths)) if widths[i] > minima[i]), key=widths.__getitem__)
            widths[widest] -= 1
        border = '+' + '+'.join('-' * (width + 2) for width in widths) + '+'
        self._print(border, code='90')
        for index, row in enumerate(cells):
            wrapped = [_wrap_cells(cell, width)
                       for cell, width in zip(row, widths)]
            for line in itertools.zip_longest(*wrapped, fillvalue=''):
                self._print('| ' + ' | '.join(part + ' ' * (width - _cell_width(part))
                                              for part, width in zip(line, widths)) + ' |',
                            code='1' if index == 0 else None)
            if index == 0:
                self._print(border, code='90')
        self._print(border, code='90')

    def notice(self, message, level='INFO'):
        self.stop()
        if not self.pretty:
            return
        color = '31' if level == 'ERROR' else '33' if level == 'WARN' else '32' if level == 'OK' else '36'
        for index, line in enumerate(_clean(message).splitlines()):
            self._print(f' [{level}] {line}' if index == 0 else ' ' + line,
                        stream=self.errors, code=color)

    def message(self, message):
        """Interactive messages are retained even in machine-output mode."""
        if self.pretty:
            self.notice(message)
        else:
            self.stop()
            self._print(message, stream=self.errors)

    def read(self, prompt):
        self.stop()
        with self._lock:
            print(self._style(_terminal_text(' > ' + str(prompt), self.errors), '1;36', self.errors),
                  end='', file=self.errors, flush=True)
        return input()

    def error(self, message):
        if self.pretty:
            self.notice(message, 'ERROR')
        else:
            self.stop()
            print(message, file=self.errors)

    def progress(self, message):
        self.notice(message, 'WORKING')
        if not self.pretty or not self.errors.isatty() or os.environ.get('TERM') == 'dumb':
            return
        self._stop.clear()

        def animate():
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

    def stop(self):
        if self._thread is not None:
            self._stop.set()
            self._thread.join()
            self._thread = None

    def __enter__(self):
        self._token = _active.set(self)
        return self

    def __exit__(self, *exc):
        self.stop()
        _active.reset(self._token)
