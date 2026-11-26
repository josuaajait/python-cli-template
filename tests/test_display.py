import contextlib
import io
import json
import os
from pathlib import Path
import re
import tempfile
import threading
import unittest
from unittest.mock import patch

from cli_template.cli import main
from cli_template.console import Console


class Terminal(io.StringIO):
    def __init__(self):
        super().__init__()
        self.animated = threading.Event()

    def isatty(self):
        return True

    def write(self, value):
        if value.startswith('\r') and value.strip():
            self.animated.set()
        return super().write(value)


class DisplayTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.logs = Path(directory.name) / 'archives'

    def run_cli(self, *args):
        output, errors = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            code = main(['--log-dir', str(self.logs), '--pretty', *args])
        return code, output.getvalue(), errors.getvalue()

    def render(self, steps, *, errors=None):
        output, errors = io.StringIO(), errors or io.StringIO()
        with patch.dict(os.environ, {'TERM': 'xterm'}), contextlib.redirect_stdout(output), \
                contextlib.redirect_stderr(errors), Console(mode='pretty', no_color=True) as console:
            steps(console)
        return output.getvalue(), errors.getvalue()

    def test_single_plain_field_is_one_line_instead_of_a_table(self):
        _, output, _ = self.run_cli('greet', 'Josua')
        self.assertIn(' Hello, Josua!', output)
        self.assertNotIn('Field', output)
        output, _ = self.render(lambda console: console.result({'status': 'SUCCESS', 'files': 3}))
        self.assertEqual(output.splitlines(), ['SUCCESS', ' Files: 3'])
        output, _ = self.render(lambda console: console.result({'status': 'SUCCESS', 'files': 3, 'size': 9}))
        self.assertIn('Field', output)

    def test_spinner_replaces_the_working_line(self):
        terminal = Terminal()

        def busy(console):
            console.progress('Hashing input')
            if console.errors is terminal:
                self.assertTrue(terminal.animated.wait(2), 'spinner never drew a frame')
            console.notice('Hashed.', 'OK')

        _, animated = self.render(busy, errors=terminal)
        self.assertIn('Hashing input', animated)
        self.assertNotIn('[WORKING]', animated)
        self.assertIn('[OK] Hashed.', animated)
        _, plain = self.render(busy)
        self.assertIn('[WORKING] Hashing input', plain)

    def test_status_is_separated_from_progress_messages(self):
        def noticed(console):
            console.notice('Done.', 'OK')
            console.result({'status': 'SUCCESS'})

        output, _ = self.render(noticed)
        self.assertEqual(output.splitlines(), ['', 'SUCCESS'])
        output, _ = self.render(lambda console: console.result({'status': 'SUCCESS'}))
        self.assertEqual(output.splitlines(), ['SUCCESS'])

    def test_archive_line_shows_short_id_with_working_show_command(self):
        code, output, _ = self.run_cli('demo', '--fail', '--delay', '0')
        self.assertEqual(code, 1)
        run, = self.logs.iterdir()
        match = re.search(r' Archive: ([0-9a-f]{8})   python-cli archives --show \1 --log-dir "(.+)"', output)
        self.assertIsNotNone(match, output)
        self.assertEqual(run.name[4:12], match.group(1))
        self.assertEqual(match.group(2), str(self.logs))
        self.assertNotIn(run.name, output)

        code, raw, _ = self.run_cli('archives', '--show', match.group(1), '--json')
        self.assertEqual((code, json.loads(raw)['id']), (0, run.name[4:]))

    def test_error_panel_matches_table_borders_and_is_spaced(self):
        failed = {'status': 'FAILED', 'error': 'Disk full', 'completed': 3, 'results': [{'step': 1}]}
        for color, corner in ((True, '╭'), (False, '+')):
            with self.subTest(color=color):
                output = Terminal()
                with patch.dict(os.environ, {'TERM': 'xterm', 'COLUMNS': '60'}), \
                        contextlib.redirect_stdout(output), contextlib.redirect_stderr(io.StringIO()), \
                        Console(mode='pretty', no_color=not color) as console:
                    console.result(failed, exit_code=1, archive=False)
                lines = [re.sub(r'\x1b\[[0-9;]*m', '', line) for line in output.getvalue().splitlines()]
                panel_top = next(index for index, line in enumerate(lines) if 'Disk full' in line) - 1
                tables = [line for line in lines if line.startswith(('╭', '+'))]
                self.assertTrue(lines[panel_top].startswith(corner), lines)
                self.assertTrue(all(line.startswith(corner) for line in tables), lines)
                self.assertEqual(lines[panel_top + 3], '', lines)

    def test_ready_flag_is_not_repeated_under_the_status(self):
        _, output, _ = self.run_cli('doctor')
        self.assertIn('READY', output)
        self.assertNotIn('Ready', output)
        output, errors = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            main(['doctor', '--json'])
        self.assertIs(json.loads(output.getvalue())['ready'], True)
        output, _ = self.render(lambda console: console.result({'ready': False}))
        self.assertIn('NOT READY', output)


if __name__ == '__main__':
    unittest.main()
