import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

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
        for flags in ([], ['--debug']):
            with patch('cli_template.cli.greet', side_effect=RuntimeError('source unavailable')):
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
