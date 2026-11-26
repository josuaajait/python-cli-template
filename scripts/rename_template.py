"""Rename this template into your own CLI in one step.

    python scripts/rename_template.py my-tool
    python scripts/rename_template.py my-tool --title "MY TOOL" --description "Does my work" --dry-run

It rewrites the distribution and command name, package folder and imports,
archive folder, log-directory environment variable, terminal title and
(optionally) description in the project's text files, then renames the package
folder. Lines containing repository URLs are left for you to update by hand.
"""
import argparse
import keyword
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
OLD_PACKAGE = 'cli_template'
OLD_DESCRIPTION = 'A reusable Python CLI starter'
TEXT_SUFFIXES = {'.py', '.md', '.toml', '.yml', '.yaml', '.cfg', '.ini', '.txt'}
SKIP_DIRECTORIES = {'.git', '.venv', 'venv', 'build', 'dist', '__pycache__', '.tmp', '.pytest_cache',
                    'htmlcov', 'node_modules'}
NAME = re.compile(r'[a-z][a-z0-9]*(?:-[a-z0-9]+)*')


def replacements(name, package, title, description):
    pairs = [
        # Longer names first: 'python-cli' is a prefix of 'python-cli-template'.
        ('python-cli-template', name),
        ('PYTHON_CLI_LOG_DIR', package.upper() + '_LOG_DIR'),
        (OLD_PACKAGE, package),
        ('python-cli', name),
        ('PYTHON CLI', title),
    ]
    if description:
        pairs.append((OLD_DESCRIPTION, description))
    return pairs


def rewrite(text, pairs):
    lines = []
    for line in text.splitlines(keepends=True):
        if 'github.com' not in line:
            for old, new in pairs:
                line = line.replace(old, new)
        lines.append(line)
    return ''.join(lines)


def project_files(root):
    script = Path(__file__).resolve()
    for path in sorted(root.rglob('*')):
        relative = path.relative_to(root).parts
        if any(part in SKIP_DIRECTORIES or part.endswith('.egg-info') for part in relative):
            continue
        if path.is_file() and path.suffix in TEXT_SUFFIXES and path.resolve() != script:
            yield path


def parse(argv):
    parser = argparse.ArgumentParser(description='Rename this template into your own CLI.')
    parser.add_argument('name', help='Distribution and command name, e.g. my-tool.')
    parser.add_argument('--package', help='Import package name (default: name with "-" replaced by "_").')
    parser.add_argument('--title', help='Terminal header title (default: name in capitals).')
    parser.add_argument('--description', help='Replaces the one-line app description.')
    parser.add_argument('--dry-run', action='store_true', help='List the files that would change.')
    args = parser.parse_args(argv)
    args.package = args.package or args.name.replace('-', '_')
    args.title = args.title or args.name.replace('-', ' ').upper()
    if not NAME.fullmatch(args.name):
        parser.error('name must be lowercase letters, digits and single hyphens, starting with a letter')
    if not args.package.isidentifier() or keyword.iskeyword(args.package) or args.package != args.package.lower():
        parser.error('package must be a lowercase Python identifier')
    return args


def main(argv=None, root=ROOT):
    args = parse(argv)
    source, target = root / OLD_PACKAGE, root / args.package
    if not source.is_dir():
        print(f'error: {source} not found; this project may already be renamed.', file=sys.stderr)
        return 2
    if target.exists():
        print(f'error: {target} already exists.', file=sys.stderr)
        return 2

    pairs = replacements(args.name, args.package, args.title, args.description)
    changes = {}
    for path in project_files(root):
        text = path.read_text(encoding='utf-8')
        updated = rewrite(text, pairs)
        if updated != text:
            changes[path] = updated

    verb = 'Would update' if args.dry_run else 'Updated'
    for path in changes:
        print(f'{verb} {path.relative_to(root).as_posix()}')
    print(f"{'Would rename' if args.dry_run else 'Renamed'} {OLD_PACKAGE}/ -> {args.package}/")
    if args.dry_run:
        return 0

    for path, text in changes.items():
        path.write_bytes(text.encode('utf-8'))
    source.rename(target)
    print('\nNext steps:')
    print('  - Update repository URLs and badges in README.md and pyproject.toml.')
    print('  - Update authors in pyproject.toml and the copyright holder in LICENSE.')
    print('  - Reinstall: python -m pip install -e .')
    print('  - Delete scripts/rename_template.py once you no longer need it.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
