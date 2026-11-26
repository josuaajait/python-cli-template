"""Declare subcommands next to their handlers instead of editing the parser.

    @command('build', help='Build project output.')
    @argument('target', nargs='?', default='dist')
    @argument('--clean', action='store_true', help='Remove old output first.')
    def build(args, console):
        return {'status': 'SUCCESS', 'target': args.target}, 0

Arguments use argparse.add_argument parameters and are listed in reading order.
Commands appear in help in the order they are defined.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Command:
    name: str
    help: str | None
    arguments: tuple
    handler: object


REGISTRY = []


def argument(*flags, **options):
    """Attach one argparse argument to the decorated handler."""
    def attach(handler):
        # Decorators apply bottom-up; inserting first keeps the reading order.
        handler.__dict__.setdefault('_cli_arguments', []).insert(0, (flags, options))
        return handler
    return attach


def command(name, *, help=None):
    """Register the decorated `(args, console) -> (result, exit_code)` handler."""
    def register(handler):
        if any(existing.name == name for existing in REGISTRY):
            raise ValueError(f'command already registered: {name}')
        REGISTRY.append(Command(name, help, tuple(getattr(handler, '_cli_arguments', ())), handler))
        return handler
    return register


def add_commands(subcommands):
    """Add every registered command to an argparse subparsers action."""
    for entry in REGISTRY:
        parser = subcommands.add_parser(entry.name, help=entry.help)
        for flags, options in entry.arguments:
            parser.add_argument(*flags, **options)
        parser.set_defaults(handler=entry.handler)
