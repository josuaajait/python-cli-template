"""Example commands. Replace these handlers with your own application logic."""
import argparse
from datetime import datetime
import hashlib
from importlib.metadata import version
import math
import os
from pathlib import Path
import platform
import re
import sys
import time
import traceback
from typing import TYPE_CHECKING, Any, NamedTuple

from . import __version__
from .archives import ArchiveSnapshot, clean_archives, find_archive, list_archives, read_result, run_id
from .commands import Result, add_commands, argument, command
from .completion import CompletionAction
from .config import ConfigError, Settings, config_path, load_settings
from .console import Console, current_console


if TYPE_CHECKING:
    from _typeshed import SupportsWrite


# Customize these values to brand your new application.
APP_NAME = 'PYTHON CLI'                # Title shown in the terminal header.
APP_DESCRIPTION = 'A reusable Python CLI starter'
PROG = 'python-cli'                    # Command name in help; match [project.scripts].
APP_ID = 'python-cli-template'         # Folder name for per-user archives.
LOG_DIR_ENV = 'PYTHON_CLI_LOG_DIR'     # Environment variable that overrides the archive folder.
CONFIG_ENV = 'PYTHON_CLI_CONFIG'      # Environment variable that points to a config file.
RICH_MINIMUM = (14, 2)                 # Keep in sync with the rich dependency in pyproject.toml.


class StyledParser(argparse.ArgumentParser):
    def print_help(self, file: 'SupportsWrite[str] | None' = None) -> None:
        console = current_console()
        if console is not None and (file is None or file is sys.stdout):
            console.header(self.prog)
        super().print_help(file)


def add_output_flags(parser: argparse.ArgumentParser) -> None:
    group = parser.add_argument_group('output')
    formats = group.add_mutually_exclusive_group()
    formats.add_argument('--pretty', dest='output_format', action='store_const', const='pretty',
                         default=argparse.SUPPRESS, help='Force readable terminal output.')
    formats.add_argument('--json', dest='output_format', action='store_const', const='json',
                         default=argparse.SUPPRESS, help='Force JSON output (automatic when piped).')
    formats.add_argument('--jsonl', dest='output_format', action='store_const', const='jsonl',
                         default=argparse.SUPPRESS,
                         help='JSON Lines: one record per stdout line, summary on stderr.')
    group.add_argument('--debug', action='store_true', default=argparse.SUPPRESS,
                       help='Show the full exception traceback on stderr.')
    group.add_argument('--log-dir', metavar='DIR', default=argparse.SUPPRESS,
                       help=f'Archive directory (also {LOG_DIR_ENV}).')
    group.add_argument('--no-archive', action='store_true', default=argparse.SUPPRESS,
                       help='Skip saving complete results for this run.')
    group.add_argument('--no-color', action='store_true', default=argparse.SUPPRESS,
                       help='Disable ANSI colors; also respects NO_COLOR.')
    group.add_argument('-q', '--quiet', action='store_true', default=argparse.SUPPRESS,
                       help='Hide progress and informational messages; warnings and results stay.')
    group.add_argument('--config', metavar='FILE', default=argparse.SUPPRESS,
                       help=f'Read defaults from this TOML file (also {CONFIG_ENV}).')


def step_count(value: str) -> int:
    number = int(value)
    if not 1 <= number <= 20:
        raise argparse.ArgumentTypeError('steps must be between 1 and 20')
    return number


class Age(NamedTuple):
    text: str
    seconds: int


_AGE_UNITS = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400, 'w': 604800}


def age(value: str) -> Age:
    match = re.fullmatch(r'(\d+)([smhdw])', value.strip().lower())
    if match is None:
        raise argparse.ArgumentTypeError('age must be a number with a unit: s, m, h, d or w (e.g. 7d)')
    return Age(match.group(0), int(match.group(1)) * _AGE_UNITS[match.group(2)])


def delay_seconds(value: str) -> float:
    number = float(value)
    if not math.isfinite(number) or not 0 <= number <= 5:
        raise argparse.ArgumentTypeError('delay must be finite and between 0 and 5 seconds')
    return number


@command('greet', help='Print a friendly structured greeting.')
@argument('name', nargs='?', default='developer')
@argument('--shout', action='store_true', help='Use uppercase text.')
def greet(args: argparse.Namespace, console: Console) -> Result:
    message = f'Hello, {args.name}!'
    return {'status': 'SUCCESS', 'message': message.upper() if args.shout else message}, 0


def release(text: str) -> tuple[int, ...]:
    """Leading numeric release parts, e.g. '14.2.0rc1' -> (14, 2, 0)."""
    parts: list[int] = []
    for part in text.split('.'):
        digits = re.match(r'\d+', part)
        if digits is None:
            break
        parts.append(int(digits.group()))
        if digits.end() != len(part):
            break
    return tuple(parts)


@command('doctor', help='Check the local Python runtime; makes no network requests.')
def doctor(args: argparse.Namespace, console: Console) -> Result:
    rich_version = version('rich')
    rich_minimum = '.'.join(map(str, RICH_MINIMUM))
    checks = [
        {'name': 'Python >=3.11', 'ok': sys.version_info >= (3, 11), 'detail': platform.python_version()},
        {'name': f'Rich >={rich_minimum}', 'ok': release(rich_version) >= RICH_MINIMUM, 'detail': rich_version},
    ]
    ready = all(check['ok'] for check in checks)
    settings: Settings = args.settings
    return {'status': 'READY' if ready else 'NOT READY', 'ready': ready, 'platform': platform.system(),
            'config': {'path': str(settings.path), 'loaded': settings.loaded}, 'checks': checks}, 0 if ready else 1


def batch_demo(console: Console) -> Result:
    faults = {17: '', 506: 'sample,abc', 998: 'sample,-1'}
    rows: list[dict[str, Any]] = []
    failures = 0
    console.progress('Validating 1,000 local sample records...')
    for number in range(1, 1001):
        record = faults.get(number, f'sample,{number}')
        row = {'item': f'item-{number:04d}', 'status': 'SUCCESS'}
        reason: str | None
        if not record:
            reason = 'Empty record'
        else:
            quantity = record.split(',')[1]
            try:
                reason = 'Negative quantity' if int(quantity) < 0 else None
            except ValueError:
                reason = 'Invalid integer'
        if reason:
            row.update(status='FAILED', reason=reason)
            failures += 1
        rows.append(row)
    console.keep('succeeded', 'failed')
    return {'status': 'FAILED' if failures else 'SUCCESS', 'succeeded': len(rows) - failures,
            'failed': failures, 'results': rows}, int(bool(failures))


@command('demo', help='Show actual sample work with progress and a results table.')
@argument('--batch', action='store_true', help='Validate 1,000 local records with three sample failures.')
@argument('--steps', type=step_count, default=3, help='Number of sample inputs (1-20).')
@argument('--delay', type=delay_seconds, default=0.35, help='Demo pacing per step, in seconds (0-5).')
@argument('--fail', action='store_true', help='Demonstrate a failed result and exit code 1.')
def demo(args: argparse.Namespace, console: Console) -> Result:
    """Hash sample inputs; delay is only for demonstrating a running spinner."""
    if args.batch:
        return batch_demo(console)
    results: list[dict[str, Any]] = []
    for step in range(1, args.steps + 1):
        console.progress(f'Step {step}/{args.steps}: hashing sample input...')
        digest = hashlib.sha256(f'cli-template-sample-{step}'.encode()).hexdigest()
        time.sleep(args.delay)
        results.append({'step': step, 'sha256': digest})
        console.notice(f'Step {step}/{args.steps} complete.', 'OK')
    result: dict[str, Any] = {'status': 'FAILED' if args.fail else 'SUCCESS',
              'completed': len(results), 'results': results}
    if args.fail:
        result['error'] = 'Intentional failure requested by --fail; completed steps are retained.'
    return result, 1 if args.fail else 0


def _saved(snapshot: ArchiveSnapshot) -> str:
    return datetime.fromtimestamp(snapshot.saved_ns / 1e9).astimezone().isoformat(timespec='seconds')


def _outcome(path: Path) -> str:
    try:
        saved = read_result(path)
    except (OSError, ValueError):
        return 'UNREADABLE'
    status = saved.get('status') if isinstance(saved, dict) else None
    return str(status) if status is not None else 'N/A'


@command('archives', help='List, show or clean saved runs.', archive=False)
@argument('--show', metavar='RUN_ID', help='Show the complete saved result of one run; an ID prefix is enough.')
@argument('--clean', action='store_true', help='Review size and confirm deletion of saved runs.')
@argument('--older-than', type=age, metavar='AGE', help='With --clean, only runs older than AGE (30m, 12h, 7d, 2w).')
@argument('--yes', action='store_true', help='With --clean, delete without asking.')
def archives(args: argparse.Namespace, console: Console) -> Result:
    if args.show is not None and args.clean:
        return {'status': 'ERROR', 'message': '--show and --clean cannot be combined.'}, 2
    if (args.older_than is not None or args.yes) and not args.clean:
        return {'status': 'ERROR', 'message': '--older-than and --yes require --clean.'}, 2
    root = console.archive_root
    entries = list_archives(root)
    size = sum(entry.size for entry in entries.values())
    result: dict[str, Any] = {'status': 'SUCCESS', 'directory': str(root), 'archives': len(entries), 'bytes': size}

    if args.show is not None:
        try:
            path = find_archive(entries, args.show)
            saved = read_result(path)
        except LookupError as error:
            return {'status': 'ERROR', 'message': str(error)}, 2
        except (OSError, ValueError) as error:
            return {'status': 'ERROR', 'message': f'Cannot read saved run: {error}'}, 2
        return {'status': 'SUCCESS', 'id': run_id(path), 'saved': _saved(entries[path]),
                'directory': str(path), 'result': saved}, 0

    if args.clean:
        targets = entries
        scope = ''
        if args.older_than is not None:
            cutoff = time.time_ns() - args.older_than.seconds * 1_000_000_000
            targets = {path: entry for path, entry in entries.items() if entry.saved_ns < cutoff}
            scope = f' older than {args.older_than.text}'
        target_size = sum(entry.size for entry in targets.values())
        result.update(matched=len(targets), removed=0)
        if targets:
            answer = 'y' if args.yes else ''
            if not args.yes:
                try:
                    answer = console.read(f'Delete {len(targets)} archives ({target_size} bytes){scope}? [y/N] ')
                except EOFError:
                    answer = ''
            if answer.strip().lower() in ('y', 'yes'):
                result['removed'] = clean_archives(targets)
        return result, 0

    newest = sorted(entries.items(), key=lambda item: item[1].saved_ns, reverse=True)
    # 'outcome', not 'status': a listed failed run is not a failure of this command.
    result['runs'] = [{'id': run_id(path), 'saved': _saved(entry), 'outcome': _outcome(path), 'bytes': entry.size}
                      for path, entry in newest]
    return result, 0


def build_parser() -> argparse.ArgumentParser:
    parser = StyledParser(prog=PROG, description=APP_DESCRIPTION)
    parser.add_argument('--version', action='version', version=f'%(prog)s {__version__}')
    parser.add_argument('--completion', action=CompletionAction,
                        help='Print a tab-completion script for SHELL (powershell, bash or zsh) and exit.')
    subcommands = parser.add_subparsers(dest='command', required=True, metavar='COMMAND')
    add_commands(subcommands)
    for subparser in (parser, *subcommands.choices.values()):
        add_output_flags(subparser)
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    # Help exits during parsing. Determine presentation preferences first so help
    # and version can be requested without running a command.
    preferences = argparse.ArgumentParser(add_help=False)
    preferences.add_argument('--pretty', dest='output_format', action='store_const', const='pretty', default='auto')
    preferences.add_argument('--json', dest='output_format', action='store_const', const='json')
    preferences.add_argument('--jsonl', dest='output_format', action='store_const', const='jsonl')
    preferences.add_argument('--no-color', action='store_true')
    early, _ = preferences.parse_known_args(arguments[:arguments.index('--')] if '--' in arguments else arguments)
    with Console(title=APP_NAME, description=APP_DESCRIPTION,
                 mode=early.output_format, no_color=early.no_color,
                 app_id=APP_ID, log_env=LOG_DIR_ENV) as console:
        args = build_parser().parse_args(arguments)
        path, explicit = config_path(getattr(args, 'config', None), app_id=APP_ID, env=CONFIG_ENV)
        try:
            settings = load_settings(path, explicit=explicit)
        except ConfigError as error:
            settings = None
            config_error = str(error)
        # Precedence: command-line flags, then environment variables, then the config file.
        args.settings = settings or Settings(path)
        console.configure(getattr(args, 'output_format', 'auto'),
                          getattr(args, 'no_color', False) or args.settings.color is False,
                          getattr(args, 'quiet', False) or bool(args.settings.quiet))
        console.log_dir = getattr(args, 'log_dir', None)
        hint = f'{PROG} archives --show {{id}}'
        console.archive_hint = hint + (f' --log-dir "{console.log_dir}"' if console.log_dir else '')
        if console.log_dir is None and not os.environ.get(LOG_DIR_ENV) and args.settings.log_dir is not None:
            console.log_dir = str(args.settings.log_dir)
        console.header(args.command)
        trace: str | None = None
        result: dict[str, Any]
        if settings is None:
            console.result({'status': 'ERROR', 'message': config_error, 'config': str(path)}, exit_code=2,
                           archive=False, debug=False)
            return 2
        try:
            result, exit_code = args.handler(args, console)
        except KeyboardInterrupt:
            result, exit_code = {'status': 'CANCELLED', 'message': 'Cancelled by user.'}, 130
        except Exception as error:
            frame = traceback.extract_tb(error.__traceback__)[-1]
            result = {'status': 'ERROR', 'message': str(error) or type(error).__name__,
                      'type': type(error).__name__, 'location': f'{frame.filename}:{frame.lineno} in {frame.name}'}
            trace = traceback.format_exc()
            exit_code = 2
        archive = args.archive_results and not getattr(args, 'no_archive', False) and settings.archive is not False
        console.result(result, exit_code=exit_code, archive=archive,
                       trace=trace, debug=getattr(args, 'debug', False))
        return exit_code
