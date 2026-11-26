import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
IGNORED = shutil.ignore_patterns('.git', '.venv', 'venv', 'build', 'dist', '__pycache__', '*.egg-info',
                                 '.tmp', '.pytest_cache')


class RenameTemplateTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.project = Path(directory.name) / 'project'
        shutil.copytree(ROOT, self.project, ignore=IGNORED)
        self.environment = {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'}
        self.environment.pop('PYTHON_CLI_LOG_DIR', None)
        self.environment['MY_TOOL_LOG_DIR'] = str(Path(directory.name) / 'logs')

    def run_in_project(self, *args):
        return subprocess.run([sys.executable, *args], cwd=self.project, env=self.environment,
                              capture_output=True, text=True, encoding='utf-8')

    def rename(self, *args):
        return self.run_in_project('scripts/rename_template.py', *args)

    def test_renamed_project_runs_under_its_new_names(self):
        result = self.rename('my-tool', '--description', 'Does my work')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.project / 'cli_template').exists())
        self.assertTrue((self.project / 'my_tool' / 'cli.py').is_file())

        help_text = self.run_in_project('-m', 'my_tool', '--help')
        self.assertEqual(help_text.returncode, 0, help_text.stderr)
        self.assertIn('usage: my-tool', help_text.stdout)
        self.assertIn('Does my work', help_text.stdout)
        self.assertIn('MY_TOOL_LOG_DIR', help_text.stdout)
        self.assertIn('MY_TOOL_CONFIG', help_text.stdout)

        doctor = self.run_in_project('-m', 'my_tool', 'doctor')
        self.assertEqual(doctor.returncode, 0, doctor.stderr)
        self.assertTrue(json.loads(doctor.stdout)['ready'])

        pretty = self.run_in_project('-m', 'my_tool', 'greet', '--pretty')
        self.assertIn('MY TOOL', pretty.stdout)

        failed = self.run_in_project('-m', 'my_tool', 'demo', '--fail', '--delay', '0')
        self.assertEqual(failed.returncode, 1, failed.stderr)
        self.assertIn(self.environment['MY_TOOL_LOG_DIR'], failed.stderr)

        pyproject = (self.project / 'pyproject.toml').read_text(encoding='utf-8')
        self.assertIn('name = "my-tool"', pyproject)
        self.assertIn('my-tool = "my_tool.cli:main"', pyproject)
        self.assertIn('include = ["my_tool*"]', pyproject)
        # Repository URLs belong to the original repository until the user changes them.
        self.assertIn('github.com/josuaajait/python-cli-template', pyproject)

        script = self.project / 'scripts' / 'rename_template.py'
        for path in self.project.rglob('*'):
            if path.is_file() and path.suffix in {'.py', '.toml', '.yml'} and path != script:
                self.assertNotIn('cli_template', path.read_text(encoding='utf-8'), path)

    def test_renamed_project_passes_its_own_test_suite(self):
        self.assertEqual(self.rename('my-tool').returncode, 0)
        (self.project / 'tests' / 'test_rename.py').unlink()
        suite = self.run_in_project('-m', 'unittest', 'discover', '-s', 'tests')
        self.assertEqual(suite.returncode, 0, suite.stderr[-2000:])

    def test_dry_run_and_invalid_names_change_nothing(self):
        before = (self.project / 'cli_template' / 'cli.py').read_text(encoding='utf-8')
        dry = self.rename('my-tool', '--dry-run')
        self.assertEqual(dry.returncode, 0, dry.stderr)
        self.assertIn('Would update cli_template/cli.py', dry.stdout)
        for name in ('My-Tool', '1tool', 'my--tool', 'my_tool'):
            with self.subTest(name=name):
                self.assertEqual(self.rename(name).returncode, 2)
        self.assertEqual(self.rename('my-tool', '--package', 'class').returncode, 2)
        self.assertEqual((self.project / 'cli_template' / 'cli.py').read_text(encoding='utf-8'), before)
        self.assertFalse((self.project / 'my_tool').exists())

    def test_second_rename_is_refused(self):
        self.assertEqual(self.rename('my-tool').returncode, 0)
        again = self.rename('other-tool')
        self.assertEqual(again.returncode, 2)
        self.assertIn('already be renamed', again.stderr)


if __name__ == '__main__':
    unittest.main()
