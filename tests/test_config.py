import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cli_template.cli import main


class Terminal(io.StringIO):
    def isatty(self):
        return True


class QuietAndConfigTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.home = self.root / 'home'
        environment = {key: value for key, value in os.environ.items()
                       if key not in ('PYTHON_CLI_CONFIG', 'PYTHON_CLI_LOG_DIR', 'NO_COLOR')}
        # Default locations point into the temporary folder, so a real user config never leaks in.
        environment.update(APPDATA=str(self.home), XDG_CONFIG_HOME=str(self.home),
                           LOCALAPPDATA=str(self.root / 'state'), XDG_STATE_HOME=str(self.root / 'state'),
                           TERM='xterm')
        patcher = patch.dict(os.environ, environment, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)
        platform = patch('cli_template.config.sys.platform', 'linux')
        platform.start()
        self.addCleanup(platform.stop)

    def run_cli(self, *args, output=None, errors=None):
        output, errors = output or io.StringIO(), errors or io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            code = main(list(args))
        return code, output.getvalue(), errors.getvalue()

    def write_config(self, text, path=None):
        path = path or self.root / 'config.toml'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
        return path

    def runs(self, folder):
        return list(folder.glob('run-*')) if folder.exists() else []

    def test_quiet_hides_progress_but_keeps_results_errors_and_archives(self):
        logs = self.root / 'logs'
        _, _, loud = self.run_cli('demo', '--pretty', '--delay', '0', '--log-dir', str(logs))
        self.assertIn('[WORKING]', loud)

        code, output, err = self.run_cli('demo', '--pretty', '--quiet', '--delay', '0')
        self.assertEqual((code, err), (0, ''))
        self.assertIn('SUCCESS', output)

        code, output, err = self.run_cli('demo', '-q', '--pretty', '--fail', '--delay', '0', '--log-dir', str(logs))
        self.assertEqual((code, err), (1, ''))
        self.assertIn('Intentional failure', output)
        self.assertIn('Archive:', output)

        code, output, err = self.run_cli('demo', '--quiet', '--fail', '--delay', '0', '--log-dir', str(logs))
        self.assertEqual((code, err), (1, ''))
        self.assertEqual(json.loads(output)['status'], 'FAILED')
        self.assertEqual(len(self.runs(logs)), 2)

    def test_config_sets_defaults_and_flags_and_environment_win(self):
        config = self.write_config('color = false\nquiet = true\nlog_dir = "saved"\n', self.root / 'cfg' / 'my.toml')
        os.environ['PYTHON_CLI_CONFIG'] = str(config)

        output, errors = Terminal(), Terminal()
        code, text, err = self.run_cli('demo', '--fail', '--delay', '0', output=output, errors=errors)
        self.assertEqual(code, 1)
        self.assertIn('FAILED', text)
        self.assertNotIn('\x1b', text)
        self.assertEqual(err, '')
        self.assertEqual(len(self.runs(config.parent / 'saved')), 1)

        os.environ['PYTHON_CLI_LOG_DIR'] = str(self.root / 'from-env')
        self.run_cli('demo', '--fail', '--delay', '0')
        self.assertEqual(len(self.runs(self.root / 'from-env')), 1)
        self.run_cli('demo', '--fail', '--delay', '0', '--log-dir', str(self.root / 'from-flag'))
        self.assertEqual(len(self.runs(self.root / 'from-flag')), 1)
        self.assertEqual(len(self.runs(config.parent / 'saved')), 1)

        other = self.write_config('archive = false\n', self.root / 'other.toml')
        code, raw, _ = self.run_cli('demo', '--fail', '--delay', '0', '--config', str(other))
        self.assertEqual(code, 1)
        self.assertEqual(len(self.runs(self.root / 'from-env')), 1)

        code, raw, _ = self.run_cli('doctor', '--json')
        self.assertEqual(json.loads(raw)['config'], {'path': str(config), 'loaded': True})

    def test_default_location_is_used_and_missing_default_is_fine(self):
        code, raw, _ = self.run_cli('doctor')
        self.assertEqual(code, 0)
        expected = self.home / 'python-cli-template' / 'config.toml'
        self.assertEqual(json.loads(raw)['config'], {'path': str(expected), 'loaded': False})

        self.write_config('archive = false\n', expected)
        self.run_cli('demo', '--fail', '--delay', '0')
        self.assertEqual(self.runs(self.root / 'state' / 'python-cli-template' / 'logs'), [])
        self.assertTrue(json.loads(self.run_cli('doctor')[1])['config']['loaded'])

    def test_invalid_config_stops_with_exit_2_but_help_still_works(self):
        cases = {
            'format = "pretty"\n': 'Unknown setting "format"',
            'quiet = "yes"\n': '"quiet"',
            'log_dir = ""\n': '"log_dir"',
            'color = \n': 'Invalid TOML',
        }
        for text, message in cases.items():
            with self.subTest(text=text):
                config = self.write_config(text)
                code, raw, _ = self.run_cli('demo', '--fail', '--delay', '0', '--config', str(config))
                self.assertEqual(code, 2)
                result = json.loads(raw)
                self.assertEqual(result['status'], 'ERROR')
                self.assertIn(message, result['message'])
                self.assertEqual(result['config'], str(config))
        missing = self.root / 'missing.toml'
        code, raw, _ = self.run_cli('greet', '--config', str(missing))
        self.assertEqual(code, 2)
        self.assertIn('not found', json.loads(raw)['message'])
        self.assertFalse((self.root / 'state').exists())

        os.environ['PYTHON_CLI_CONFIG'] = str(self.write_config('nonsense = 1\n'))
        with self.assertRaises(SystemExit) as stop, contextlib.redirect_stdout(io.StringIO()):
            main(['--help'])
        self.assertEqual(stop.exception.code, 0)


if __name__ == '__main__':
    unittest.main()
