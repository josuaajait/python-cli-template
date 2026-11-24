import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


class Terminal(io.StringIO):
    def isatty(self):
        return True


class AsciiTerminal(Terminal):
    @property
    def encoding(self):
        return 'ascii'

    def __init__(self):
        super().__init__()
        self.animated = threading.Event()

    def write(self, value):
        value.encode('ascii')
        if value.startswith('\r'):
            self.animated.set()
        return super().write(value)


class CliTests(unittest.TestCase):
    def command(self, *args):
        return subprocess.run([sys.executable, '-m', 'cli_template', *args], cwd=ROOT,
                              capture_output=True, text=True, encoding='utf-8')

    def test_greeting_from_module(self):
        result = self.command('greet', 'Mikhael')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['message'], 'Hello, Mikhael!')
        self.assertEqual(result.stderr, '')

    def test_output_flags_work_before_or_after_subcommand(self):
        for flag in ('--pretty', '--json'):
            for args in ([flag, 'greet', 'Mikhael'], ['greet', 'Mikhael', flag]):
                with self.subTest(args=args):
                    result = self.command(*args)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    if flag == '--json':
                        self.assertEqual(json.loads(result.stdout)['status'], 'SUCCESS')
                    else:
                        self.assertIn('PYTHON CLI', result.stdout)
                    self.assertNotIn('\x1b', result.stdout)

    def test_pipe_demo_retains_steps_and_one_json_result(self):
        result = self.command('demo', '--steps', '2', '--delay', '0')
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data['completed'], 2)
        self.assertEqual(len(data['results']), 2)
        self.assertEqual(len(data['results'][0]['sha256']), 64)
        self.assertEqual(result.stderr, '')

    def test_failed_demo_reports_failure_with_completed_work(self):
        result = self.command('demo', '--steps', '2', '--delay', '0', '--fail', '--no-archive')
        self.assertEqual(result.returncode, 1)
        data = json.loads(result.stdout)
        self.assertEqual(data['status'], 'FAILED')
        self.assertEqual(data['completed'], 2)
        self.assertIn('error', data)

    def test_invalid_step_counts_and_nonfinite_delays_fail_before_work(self):
        for args in (['--steps', '0'], ['--steps', '21'], ['--delay', 'nan'],
                     ['--delay', 'inf'], ['--delay', '-1']):
            with self.subTest(args=args):
                result = self.command('demo', *args)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, '')
                self.assertNotIn('Traceback', result.stderr)

    def test_help_and_version_work_without_running_a_command(self):
        for args in (['--help'], ['demo', '--help'], ['--version']):
            with self.subTest(args=args):
                result = self.command(*args)
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_doctor_reports_ready_runtime(self):
        result = self.command('doctor')
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertTrue(data['ready'])
        self.assertEqual(data['status'], 'READY')

    def test_terminal_auto_formatting_and_explicit_json_do_not_leak_state(self):
        from cli_template.cli import main
        for flags in ([], ['--json'], []):
            output = Terminal()
            with contextlib.redirect_stdout(output), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main(['greet', 'Mikhael', *flags]), 0)
            if flags:
                self.assertEqual(json.loads(output.getvalue())['status'], 'SUCCESS')
            else:
                self.assertIn('PYTHON CLI', output.getvalue())

    def test_interrupt_returns_130_and_stops_spinner(self):
        from cli_template.cli import main
        output = io.StringIO()
        with patch('cli_template.cli.time.sleep', side_effect=KeyboardInterrupt), \
                contextlib.redirect_stdout(output), contextlib.redirect_stderr(Terminal()):
            self.assertEqual(main(['demo', '--json']), 130)
        self.assertEqual(json.loads(output.getvalue())['status'], 'CANCELLED')
        self.assertFalse(any(t.name == 'cli-spinner' for t in threading.enumerate()))


class ConsoleTests(unittest.TestCase):
    def render(self, value, *, columns='88', environment=None, **options):
        from cli_template.console import Console
        output = Terminal()
        with patch.dict(os.environ, {'COLUMNS': columns, 'TERM': 'xterm', **(environment or {})}, clear=True), \
                contextlib.redirect_stdout(output), contextlib.redirect_stderr(io.StringIO()):
            with Console(mode='pretty', **options) as console:
                console.header('demo')
                console.result(value)
        return output.getvalue()

    def test_branding_is_customizable_and_has_no_critic_agent_semantics(self):
        text = self.render({'status': 'SUCCESS'}, title='MY APP', description='My command line tool')
        self.assertIn('MY APP', text)
        self.assertIn('My command line tool', text)
        for old in ('CRITIC AGENT', 'Laravel', 'LOLOS', 'Qwen'):
            self.assertNotIn(old, text)

    def test_false_zero_null_empty_and_unknown_status_remain_visible(self):
        text = self.render({'status': 'UNREVIEWED', 'reviewed': False, 'count': 0,
                            'metric': None, 'empty': {}, 'rows': []}, no_color=True)
        for expected in ('UNREVIEWED', 'no', '0', 'N/A', '(empty)'):
            self.assertIn(expected, text)
        self.assertNotIn('SUCCESS', text)

    def test_empty_or_control_only_keys_do_not_create_zero_width_columns(self):
        for row in ({'': ''}, {'\x1b[2J': ''}):
            with self.subTest(row=row):
                text = self.render({'rows': [row]}, no_color=True)
                self.assertIn('RESULT', text)
                self.assertNotIn('\x1b', text)

    def test_nested_rows_and_long_paths_wrap_in_narrow_terminal(self):
        text = self.render({'path': 'C:/long-project-name/long-run-name/output.json',
                            'rows': [{'step': 1, 'valid': True, 'value': 0,
                                      'issue': None, 'description': 'all values retained'}]},
                           columns='36', no_color=True)
        self.assertTrue(all(len(line) <= 35 for line in text.splitlines()), text)
        self.assertIn('output.json', text.replace('\n', '').replace(' ', '').replace('|', ''))

    def test_wide_unicode_values_fit_terminal_cells_and_keep_table_borders(self):
        text = self.render({'message': '\u754c' * 40}, columns='36', no_color=True)
        self.assertEqual(text.count('\u754c'), 40)
        for line in text.splitlines():
            cells = len(line.replace('\u754c', '')) + 2 * line.count('\u754c')
            self.assertLessEqual(cells, 35, line)
        table_lines = [line for line in text.splitlines() if line.startswith(('+', '|'))]
        border_width = len(table_lines[0])
        for line in table_lines:
            self.assertEqual(len(line.replace('\u754c', '')) + 2 * line.count('\u754c'), border_width)

    def test_no_color_and_dumb_terminal_disable_ansi(self):
        self.assertIn('\x1b[', self.render({'status': 'SUCCESS'}))
        for environment in ({'NO_COLOR': ''}, {'TERM': 'dumb'}):
            with self.subTest(environment=environment):
                self.assertNotIn('\x1b', self.render({'status': 'SUCCESS'}, environment=environment))

    def test_terminal_controls_are_removed_only_from_pretty_view(self):
        from cli_template.console import Console
        payload = {'detail': '\x1b[2Jhello\x1b]0;bad-title\x07'}
        text = self.render(payload, no_color=True)
        self.assertNotIn('\x1b', text)
        self.assertNotIn('bad-title', text)
        output = io.StringIO()
        with contextlib.redirect_stdout(output), Console(mode='json') as console:
            console.result(payload)
        self.assertEqual(json.loads(output.getvalue()), payload)

    def test_spinner_stops_before_read_and_after_exception(self):
        from cli_template.console import Console
        with contextlib.redirect_stdout(Terminal()), contextlib.redirect_stderr(Terminal()):
            with self.assertRaises(RuntimeError):
                with Console(mode='pretty') as console:
                    console.progress('Preparing')
                    with patch('builtins.input', return_value='yes'):
                        self.assertEqual(console.read('Continue? '), 'yes')
                    self.assertFalse(any(t.name == 'cli-spinner' for t in threading.enumerate()))
                    console.progress('Working')
                    raise RuntimeError('cancel')
        self.assertFalse(any(t.name == 'cli-spinner' for t in threading.enumerate()))

    def test_spinner_and_input_support_legacy_console_encodings(self):
        from cli_template.console import Console
        errors = AsciiTerminal()
        thread_errors = []
        with contextlib.redirect_stdout(AsciiTerminal()), contextlib.redirect_stderr(errors), \
                patch.dict(os.environ, {'TERM': 'xterm'}), \
                patch('threading.excepthook', lambda event: thread_errors.append(event.exc_value)):
            with Console(mode='pretty') as console:
                console.progress('Working \U0001f680')
                self.assertTrue(errors.animated.wait(1), 'spinner failed to render a frame')
                with patch('builtins.input', return_value='yes'):
                    self.assertEqual(console.read('Continue \U0001f680? '), 'yes')
        self.assertEqual(thread_errors, [])
        self.assertIn('Working ?', errors.getvalue())
        self.assertIn('Continue ?? ', errors.getvalue())

    def test_json_preserves_unicode_data_on_legacy_console_encoding(self):
        from cli_template.console import Console
        output = AsciiTerminal()
        with contextlib.redirect_stdout(output), Console(mode='json') as console:
            console.result({'message': 'Hello \U0001f680'})
        self.assertEqual(json.loads(output.getvalue()), {'message': 'Hello \U0001f680'})


if __name__ == '__main__':
    unittest.main()
