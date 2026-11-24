"""Example commands. Replace these handlers with your own application logic."""
import argparse
import hashlib
import math
import platform
import sys
import time

from . import __version__
from .console import Console, current_console


# Customize these two values to brand your new application.
APP_NAME = 'PYTHON CLI'
APP_DESCRIPTION = 'A reusable Python CLI starter'


class StyledParser(argparse.ArgumentParser):
    def print_help(self, file=None):
        console = current_console()
        if console is not None and (file is None or file is sys.stdout):
            console.header(self.prog)
        super().print_help(file)


def add_output_flags(parser):
    group = parser.add_argument_group('output')
    formats = group.add_mutually_exclusive_group()
    formats.add_argument('--pretty', dest='output_format', action='store_const', const='pretty',
                         default=argparse.SUPPRESS, help='Force readable terminal output.')
    formats.add_argument('--json', dest='output_format', action='store_const', const='json',
                         default=argparse.SUPPRESS, help='Force JSON output (automatic when piped).')
    group.add_argument('--no-color', action='store_true', default=argparse.SUPPRESS,
                       help='Disable ANSI colors; also respects NO_COLOR.')


def step_count(value):
    number = int(value)
    if not 1 <= number <= 20:
        raise argparse.ArgumentTypeError('steps must be between 1 and 20')
    return number


def delay_seconds(value):
    number = float(value)
    if not math.isfinite(number) or not 0 <= number <= 5:
        raise argparse.ArgumentTypeError('delay must be finite and between 0 and 5 seconds')
    return number


def greet(args, console):
    message = f'Hello, {args.name}!'
    return {'status': 'SUCCESS', 'message': message.upper() if args.shout else message}, 0


def doctor(args, console):
    checks = [
        {'name': 'Python >=3.11', 'ok': sys.version_info >= (3, 11), 'detail': platform.python_version()},
        {'name': 'Standard library', 'ok': True, 'detail': 'No runtime dependencies required'},
    ]
    ready = all(check['ok'] for check in checks)
    return {'status': 'READY' if ready else 'NOT READY', 'ready': ready,
            'platform': platform.system(), 'checks': checks}, 0 if ready else 1


def demo(args, console):
    """Hash sample inputs; delay is only for demonstrating a running spinner."""
    results = []
    for step in range(1, args.steps + 1):
        console.progress(f'Step {step}/{args.steps}: hashing sample input...')
        digest = hashlib.sha256(f'cli-template-sample-{step}'.encode()).hexdigest()
        time.sleep(args.delay)
        results.append({'step': step, 'sha256': digest})
        console.notice(f'Step {step}/{args.steps} complete.', 'OK')
    result = {'status': 'FAILED' if args.fail else 'SUCCESS',
              'completed': len(results), 'results': results}
    if args.fail:
        result['error'] = 'Intentional failure requested by --fail; completed steps are retained.'
    return result, 1 if args.fail else 0


def build_parser():
    parser = StyledParser(prog='python-cli', description=APP_DESCRIPTION)
    parser.add_argument('--version', action='version', version=f'%(prog)s {__version__}')
    subcommands = parser.add_subparsers(dest='command', required=True, metavar='COMMAND')
    hello = subcommands.add_parser('greet', help='Print a friendly structured greeting.')
    hello.add_argument('name', nargs='?', default='developer')
    hello.add_argument('--shout', action='store_true', help='Use uppercase text.')
    hello.set_defaults(handler=greet)
    health = subcommands.add_parser('doctor', help='Check the local Python runtime; makes no network requests.')
    health.set_defaults(handler=doctor)
    example = subcommands.add_parser('demo', help='Show actual sample work with progress and a results table.')
    example.add_argument('--steps', type=step_count, default=3, help='Number of sample inputs (1-20).')
    example.add_argument('--delay', type=delay_seconds, default=0.35,
                         help='Demo pacing per step, in seconds (0-5).')
    example.add_argument('--fail', action='store_true', help='Demonstrate a failed result and exit code 1.')
    example.set_defaults(handler=demo)
    for command in (parser, *subcommands.choices.values()):
        add_output_flags(command)
    return parser


def main(argv=None):
    arguments = list(sys.argv[1:] if argv is None else argv)
    # Help exits during parsing. Determine presentation preferences first so help
    # and version can be requested without running a command.
    preferences = argparse.ArgumentParser(add_help=False)
    preferences.add_argument('--pretty', dest='output_format', action='store_const', const='pretty', default='auto')
    preferences.add_argument('--json', dest='output_format', action='store_const', const='json')
    preferences.add_argument('--no-color', action='store_true')
    early, _ = preferences.parse_known_args(arguments[:arguments.index('--')] if '--' in arguments else arguments)
    with Console(title=APP_NAME, description=APP_DESCRIPTION,
                 mode=early.output_format, no_color=early.no_color) as console:
        args = build_parser().parse_args(arguments)
        console.configure(getattr(args, 'output_format', 'auto'), getattr(args, 'no_color', False))
        console.header(args.command)
        try:
            result, exit_code = args.handler(args, console)
            console.result(result)
            return exit_code
        except KeyboardInterrupt:
            console.result({'status': 'CANCELLED', 'message': 'Cancelled by user.'})
            return 130
        except (OSError, ValueError) as error:
            console.result({'status': 'ERROR', 'message': str(error)})
            return 2
