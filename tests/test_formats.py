import contextlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from cli_template import commands
from cli_template.cli import PROG, main
from cli_template.console import Console


ROOT = Path(__file__).resolve().parents[1]
# Derived from the branding, so the tests still pass after scripts/rename_template.py.
FUNCTION = '_' + re.sub(r'\W', '_', PROG) + '_complete'


class FormatTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.logs = self.root / 'archives'

    def run_cli(self, *args):
        output, errors = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            code = main(['--log-dir', str(self.logs), *args])
        return code, output.getvalue(), errors.getvalue()

    def completion(self, shell):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), self.assertRaises(SystemExit) as stop:
            main(['--completion', shell])
        self.assertEqual(stop.exception.code, 0)
        path = self.root / f'completion.{"ps1" if shell == "powershell" else "sh"}'
        path.write_text(output.getvalue(), encoding='utf-8')
        return output.getvalue(), path

    # JSON Lines

    def test_jsonl_writes_one_record_per_line_and_summary_to_stderr(self):
        code, output, errors = self.run_cli('demo', '--batch', '--jsonl')
        self.assertEqual(code, 1)
        records = [json.loads(line) for line in output.splitlines()]
        self.assertEqual(len(records), 1000)
        self.assertEqual(records[16], {'item': 'item-0017', 'status': 'FAILED', 'reason': 'Empty record'})
        summary_line, archive_line = errors.splitlines()
        self.assertEqual(json.loads(summary_line), {'status': 'FAILED', 'succeeded': 997, 'failed': 3})
        self.assertTrue(archive_line.startswith('Archive: '))
        run, = self.logs.iterdir()
        self.assertEqual(json.loads((run / 'result.json').read_text('utf-8'))['results'], records)

        code, output, errors = self.run_cli('demo', '--batch', '--jsonl', '--quiet')
        self.assertEqual((code, len(output.splitlines()), errors), (1, 1000, ''))

    def test_jsonl_without_one_clear_list_writes_the_whole_result_on_one_line(self):
        code, output, errors = self.run_cli('greet', 'Josua', '--jsonl')
        self.assertEqual((code, errors), (0, ''))
        self.assertEqual(output.splitlines(), ['{"status": "SUCCESS", "message": "Hello, Josua!"}'])

        value = {'status': 'SUCCESS', 'files': ['a', 'b'], 'dirs': ['c']}
        for chosen, expected in ((None, [value]), ('dirs', ['c'])):
            with self.subTest(records=chosen):
                output, errors = io.StringIO(), io.StringIO()
                with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors), \
                        Console(mode='jsonl') as console:
                    if chosen:
                        console.records(chosen)
                    console.result(value, archive=False)
                self.assertEqual([json.loads(line) for line in output.getvalue().splitlines()], expected)

    def test_jsonl_is_exclusive_with_other_formats(self):
        with self.assertRaises(SystemExit) as stop, contextlib.redirect_stderr(io.StringIO()):
            self.run_cli('greet', '--jsonl', '--json')
        self.assertEqual(stop.exception.code, 2)

    # Shell completion

    def test_completion_scripts_list_commands_and_their_options(self):
        for shell in ('powershell', 'bash', 'zsh'):
            with self.subTest(shell=shell):
                script, _ = self.completion(shell)
                for word in ('greet', 'doctor', 'demo', 'archives', '--batch', '--older-than', '--jsonl'):
                    self.assertIn(word, script)
                self.assertNotIn('PYTHON CLI', script)
        self.assertIn('bashcompinit', self.completion('zsh')[0])
        with self.assertRaises(SystemExit) as stop, contextlib.redirect_stderr(io.StringIO()):
            main(['--completion', 'fish'])
        self.assertEqual(stop.exception.code, 2)

    def test_completion_includes_newly_registered_commands(self):
        with patch('cli_template.commands.REGISTRY', list(commands.REGISTRY)):
            @commands.command('deploy', help='Deploy.')
            @commands.argument('--target')
            def deploy(args, console):
                return {'status': 'SUCCESS'}, 0

            script, _ = self.completion('bash')
        self.assertIn('deploy) words="-h --help --target', script)

    @unittest.skipIf(os.name == 'nt' or shutil.which('bash') is None, 'needs a POSIX bash')
    def test_bash_completion_completes_commands_and_options(self):
        _, path = self.completion('bash')
        for words, expected in ((['dem'], 'demo'), (['demo', '--b'], '--batch'),
                                (['archives', '--sh'], '--show'), (['demo', '--json', '--st'], '--steps')):
            with self.subTest(words=words):
                quoted = ' '.join(f"'{word}'" for word in words)
                script = (f'source "{path}"; COMP_WORDS=(python-cli {quoted}); COMP_CWORD={len(words)}; '
                          f'{FUNCTION}; echo "${{COMPREPLY[*]}}"')
                result = subprocess.run(['bash', '-c', script], capture_output=True, text=True)
                self.assertEqual(result.stdout.strip(), expected, result.stderr)

    @unittest.skipIf(shutil.which('pwsh') is None and shutil.which('powershell') is None, 'needs PowerShell')
    def test_powershell_completion_completes_commands_and_options(self):
        _, path = self.completion('powershell')
        probe = self.root / 'probe.ps1'
        probe.write_text(
            '. $args[0]\n'
            "foreach ($line in @('python-cli dem', 'python-cli demo --b', 'python-cli archives --sh')) {\n"
            '    $found = TabExpansion2 -inputScript $line -cursorColumn $line.Length\n'
            "    ($found.CompletionMatches | ForEach-Object CompletionText) -join ' '\n"
            '}\n', encoding='utf-8')
        shell = shutil.which('pwsh') or shutil.which('powershell')
        result = subprocess.run([shell, '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(probe), str(path)],
                                capture_output=True, text=True, timeout=120)
        self.assertEqual(result.stdout.split(), ['demo', '--batch', '--show'], result.stderr)

    def test_completion_prints_only_the_script_for_the_installed_command_name(self):
        result = subprocess.run([sys.executable, '-m', 'cli_template', '--completion', 'bash'], cwd=ROOT,
                                capture_output=True, text=True, encoding='utf-8')
        self.assertEqual((result.returncode, result.stderr), (0, ''))
        self.assertTrue(result.stdout.startswith(FUNCTION + '() {'))
        self.assertTrue(result.stdout.endswith(f'complete -o default -F {FUNCTION} {PROG}\n'))


if __name__ == '__main__':
    unittest.main()
