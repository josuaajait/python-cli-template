import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

from cli_template import commands
from cli_template.cli import main
from cli_template.console import Console


class PresentationTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.logs = Path(directory.name) / 'archives'

    def run_cli(self, *args):
        output, errors = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            code = main(['--log-dir', str(self.logs), *args])
        return code, output.getvalue(), errors.getvalue()

    def test_batch_preview_and_archive_match_complete_pipeline(self):
        code, pretty, _ = self.run_cli('demo', '--batch', '--pretty', '--no-color')
        self.assertEqual(code, 1)
        self.assertIn('997 succeeded', pretty)
        self.assertIn('3 failed', pretty)
        self.assertLess(len(pretty.splitlines()), 55)
        code, raw, diagnostic = self.run_cli('demo', '--batch', '--json')
        payload = json.loads(raw)
        self.assertEqual(len(payload['results']), 1000)
        failures = [row for row in payload['results'] if row['status'] == 'FAILED']
        self.assertEqual(len(failures), 3)
        for row in failures:
            self.assertIn(row['item'], pretty)
            self.assertIn(row['reason'], pretty)
        archives = list(self.logs.iterdir())
        self.assertEqual(len(archives), 2)
        for archive in archives:
            self.assertEqual(json.loads((archive / 'result.json').read_text('utf-8')), payload)
            self.assertIn('item-1000', (archive / 'result.log').read_text('utf-8'))
        self.assertIn('Archive', diagnostic)

    def test_simple_output_and_disabled_archiving_make_no_files(self):
        self.assertEqual(self.run_cli('greet')[0], 0)
        self.assertEqual(self.run_cli('demo', '--batch', '--no-archive')[0], 1)
        self.assertFalse(self.logs.exists())

    def test_grouping_and_pinned_fields(self):
        records = [{'item': f'entry-{i}', 'status': 'FAILED',
                    'reason': 'missing' if i % 2 else 'invalid'} for i in range(30)]
        value = {'results': records, 'required_items': [f'core-{i}' for i in range(15)]}
        out = io.StringIO()
        with contextlib.redirect_stdout(out), Console(mode='pretty', no_color=True) as console:
            console.keep('required_items')
            console.result(value, archive=False)
        view = out.getvalue()
        self.assertIn('core-14', view)
        self.assertLess(view.index('core-14'), view.index('Results'))
        for reason in ('missing', 'invalid'):
            self.assertIn(reason, view)
        self.assertIn('15', view)
        self.assertIn('entry-0', view)
        self.assertIn('entry-1', view)
        self.assertNotIn('entry-29', view)

    def test_archive_failure_outputs_all_rows_and_keeps_exit_code(self):
        self.logs.write_text('occupied')
        code, out, err = self.run_cli('demo', '--batch', '--pretty')
        self.assertEqual(code, 1)
        self.assertIn('997 succeeded', out)
        self.assertIn('archive', err.lower())
        self.assertIn('item-1000', err)
        self.assertIn('item-0001', err)

    def test_handler_exception_has_location_and_debug_trace(self):
        failing = Mock(side_effect=RuntimeError('source unavailable'))
        registry = [commands.Command(entry.name, entry.help, entry.arguments, failing)
                    if entry.name == 'greet' else entry for entry in commands.REGISTRY]
        for flags in ([], ['--debug']):
            with patch('cli_template.commands.REGISTRY', registry):
                code, raw, err = self.run_cli('greet', *flags)
            self.assertEqual(code, 2)
            self.assertIn('source unavailable', json.loads(raw)['message'])
            self.assertTrue(json.loads(raw)['location'])
            self.assertEqual('Traceback' in err, bool(flags))
        for archive in self.logs.iterdir():
            self.assertIn('Traceback', (archive / 'result.log').read_text('utf-8'))

    def test_archive_cleanup_previews_size_and_requires_confirmation(self):
        self.run_cli('demo', '--fail', '--delay', '0')
        unrelated = self.logs / 'keep.txt'
        unrelated.write_text('mine')
        _, raw, _ = self.run_cli('archives')
        preview = json.loads(raw)
        self.assertEqual(preview['archives'], 1)
        self.assertGreater(preview['bytes'], 0)
        with patch('builtins.input', return_value='n'):
            self.run_cli('archives', '--clean')
        self.assertEqual(len(list(self.logs.iterdir())), 2)
        with patch('builtins.input', return_value='y'):
            _, raw, err = self.run_cli('archives', '--clean')
        self.assertEqual(json.loads(raw)['removed'], 1)
        self.assertIn(str(preview['bytes']), err)
        self.assertEqual(list(self.logs.iterdir()), [unrelated])

    def save_runs(self, count, *, days_old=()):
        for _ in range(count):
            self.run_cli('demo', '--fail', '--delay', '0')
        runs = sorted(self.logs.iterdir())
        for index, run in enumerate(runs):
            # Distinct, known ages: run 0 is newest; listed ages in days_old are pushed back.
            seconds = days_old[index] * 86400 if index < len(days_old) else index * 60
            stamp = time.time() - seconds
            for name in ('result.json', 'result.log'):
                os.utime(run / name, (stamp, stamp))
        return runs

    def test_archive_listing_is_newest_first_and_never_archives_itself(self):
        runs = self.save_runs(10)
        code, raw, _ = self.run_cli('archives', '--json')
        self.assertEqual(code, 0)
        listing = json.loads(raw)
        self.assertEqual(listing['archives'], 10)
        self.assertEqual([run['id'] for run in listing['runs']], [run.name[4:] for run in runs])
        self.assertEqual({run['outcome'] for run in listing['runs']}, {'FAILED'})
        self.assertEqual([run['saved'] for run in listing['runs']], sorted((r['saved'] for r in listing['runs']),
                                                                         reverse=True))

        code, output, _ = self.run_cli('archives', '--pretty')
        self.assertEqual(code, 0)
        self.assertIn('SUCCESS', output)
        self.assertIn('10 total; 2 rows omitted from preview.', output)
        self.assertIn('Full result: use --json.', output)
        self.assertIn(listing['runs'][0]['id'], output)
        self.assertNotIn(listing['runs'][9]['id'], output)
        self.assertEqual(len(list(self.logs.iterdir())), 10)

    def test_show_returns_complete_saved_result_by_id_prefix(self):
        self.run_cli('demo', '--batch')
        run, = self.logs.iterdir()
        code, raw, _ = self.run_cli('archives', '--show', run.name[4:10].upper())
        self.assertEqual(code, 0)
        shown = json.loads(raw)
        self.assertEqual(shown['id'], run.name[4:])
        self.assertEqual(shown['result'], json.loads((run / 'result.json').read_text('utf-8')))
        self.assertEqual(len(shown['result']['results']), 1000)
        self.assertEqual(self.run_cli('archives', '--show', run.name)[0], 0)

        run.rename(self.logs / ('run-' + 'a' * 31 + '1'))
        self.run_cli('demo', '--fail', '--delay', '0')
        other, = (path for path in self.logs.iterdir() if not path.name.startswith('run-aaaa'))
        other.rename(self.logs / ('run-' + 'a' * 31 + '2'))
        for prefix, message in (('aaaa', '2 saved runs match'), ('b', 'No saved run matches'),
                                ('xyz', 'hexadecimal')):
            with self.subTest(prefix=prefix):
                code, raw, _ = self.run_cli('archives', '--show', prefix)
                self.assertEqual(code, 2)
                self.assertIn(message, json.loads(raw)['message'])
        self.assertEqual(len(list(self.logs.iterdir())), 2)

    def test_clean_can_target_old_runs_without_asking(self):
        runs = self.save_runs(3, days_old=(10, 0, 8))
        with patch('builtins.input', side_effect=AssertionError('--yes must not prompt')):
            code, raw, _ = self.run_cli('archives', '--clean', '--older-than', '7d', '--yes')
        self.assertEqual(code, 0)
        result = json.loads(raw)
        self.assertEqual((result['matched'], result['removed']), (2, 2))
        self.assertEqual(list(self.logs.iterdir()), [runs[1]])

        with patch('builtins.input', return_value='y'):
            _, raw, err = self.run_cli('archives', '--clean', '--older-than', '1w')
        self.assertEqual((json.loads(raw)['matched'], json.loads(raw)['removed']), (0, 0))
        self.assertEqual(err, '')
        stamp = time.time() - 60
        for name in ('result.json', 'result.log'):
            os.utime(runs[1] / name, (stamp, stamp))
        with patch('builtins.input', return_value='y'):
            _, raw, err = self.run_cli('archives', '--clean', '--older-than', '30s')
        self.assertEqual(json.loads(raw)['removed'], 1)
        self.assertIn('Delete 1 archives', err)
        self.assertIn('older than 30s', err)
        self.assertEqual(list(self.logs.iterdir()), [])

    def test_archive_options_reject_invalid_combinations(self):
        for args in (['--older-than', '7d'], ['--yes'], ['--show', 'abc', '--clean']):
            with self.subTest(args=args):
                code, raw, _ = self.run_cli('archives', *args)
                self.assertEqual(code, 2)
                self.assertEqual(json.loads(raw)['status'], 'ERROR')
        for bad in ('7', '7x', '-1d'):
            with self.subTest(age=bad), self.assertRaises(SystemExit) as stop, \
                    contextlib.redirect_stderr(io.StringIO()):
                self.run_cli('archives', '--clean', '--older-than', bad)
            self.assertEqual(stop.exception.code, 2)
        self.assertFalse(self.logs.exists())

    def test_cleanup_skips_archive_modified_after_preview(self):
        self.run_cli('demo', '--fail', '--delay', '0')
        archive, = self.logs.iterdir()

        def edit_then_confirm():
            (archive / 'result.log').write_text('Changed after preview.')
            return 'y'

        with patch('builtins.input', side_effect=edit_then_confirm):
            code, raw, _ = self.run_cli('archives', '--clean')
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(raw)['removed'], 0)
        self.assertEqual((archive / 'result.log').read_text(), 'Changed after preview.')

    def test_successful_summary_preserves_exit_code_on_archive_failure(self):
        self.logs.write_text('occupied')
        code, _, err = self.run_cli('demo', '--pretty', '--steps', '9', '--delay', '0')
        self.assertEqual(code, 0)
        self.assertIn('Cannot save archive', err)
        self.assertIn('"step": 9', err)

    def test_branding_controls_command_name_and_archive_location(self):
        state = Path(self.logs.parent) / 'state'
        environment = {'LOCALAPPDATA': str(state), 'XDG_STATE_HOME': str(state), 'MY_APP_LOGS': ''}
        with (patch('cli_template.cli.PROG', 'my-app'), patch('cli_template.cli.APP_ID', 'my-app'),
              patch('cli_template.cli.LOG_DIR_ENV', 'MY_APP_LOGS'), patch.dict('os.environ', environment),
              patch('cli_template.archives.sys.platform', 'linux')):
            output = io.StringIO()
            with contextlib.redirect_stdout(output), self.assertRaises(SystemExit):
                main(['--help'])
            self.assertIn('usage: my-app', output.getvalue())
            self.assertIn('MY_APP_LOGS', output.getvalue())

            output, errors = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
                self.assertEqual(main(['demo', '--fail', '--delay', '0', '--json']), 1)
            self.assertEqual(len(list((state / 'my-app' / 'logs').glob('run-*'))), 1)

            override = Path(self.logs.parent) / 'override'
            with (patch.dict('os.environ', {'MY_APP_LOGS': str(override)}),
                  contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO())):
                self.assertEqual(main(['demo', '--fail', '--delay', '0', '--json']), 1)
            self.assertEqual(len(list(override.glob('run-*'))), 1)

    def test_decorated_command_gets_arguments_output_flags_and_help(self):
        with patch('cli_template.commands.REGISTRY', list(commands.REGISTRY)):
            @commands.command('count', help='Count words.')
            @commands.argument('words', nargs='+')
            @commands.argument('--unique', action='store_true', help='Ignore repeated words.')
            def count(args, console):
                words = set(args.words) if args.unique else args.words
                return {'status': 'SUCCESS', 'count': len(words)}, 0

            code, output, _ = self.run_cli('count', 'a', 'b', 'a', '--unique', '--json')
            self.assertEqual((code, json.loads(output)['count']), (0, 2))
            code, output, _ = self.run_cli('--pretty', 'count', 'a', 'a')
            self.assertEqual(code, 0)
            self.assertIn('2', output)

            help_text = io.StringIO()
            with contextlib.redirect_stdout(help_text), self.assertRaises(SystemExit):
                main(['--help'])
            self.assertIn('Count words.', help_text.getvalue())
            self.assertLess(help_text.getvalue().index('archives'), help_text.getvalue().index('count'))

            with self.assertRaises(ValueError):
                commands.command('count')(count)
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            main(['count', 'a'])

    def test_doctor_rejects_rich_older_than_minimum(self):
        for installed, ready in (('14.1.9', False), ('14.2.0', True), ('15.0.0rc1', True)):
            with self.subTest(installed=installed), patch('cli_template.cli.version', return_value=installed):
                code, output, _ = self.run_cli('doctor', '--json')
                data = json.loads(output)
                self.assertEqual(code, 0 if ready else 1)
                self.assertEqual(data['ready'], ready)
                self.assertEqual(data['checks'][1]['detail'], installed)

    def test_windows_without_color_support_uses_plain_text(self):
        class Terminal(io.StringIO):
            def isatty(self):
                return True

        out = Terminal()
        with patch.dict('os.environ', {}, clear=True), patch('cli_template.console.os.name', 'nt'), \
                contextlib.redirect_stdout(out), Console() as console:
            console.header('greet')
            console.result({'status': 'SUCCESS', 'message': 'hello'})
        self.assertIn('hello', out.getvalue())
        self.assertNotIn('\x1b', out.getvalue())
