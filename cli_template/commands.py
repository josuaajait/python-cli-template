"""Declare subcommands next to their handlers instead of editing the parser.

    @command('build', help='Build project output.')
    @argument('target', nargs='?', default='dist')
    @argument('--clean', action='store_true', help='Remove old output first.')
    def build(args, console):
        return {'status': 'SUCCESS', 'target': args.target}, 0

Arguments use argparse.add_argument parameters and are listed in reading order.
Commands appear in help in the order they are defined.
"""
from __future__ import annotations

import argparse
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, TypeVar


if TYPE_CHECKING:
    from .console import Console


Result = tuple[dict[str, Any], int]
Handler = Callable[[argparse.Namespace, 'Console'], Result]
ArgumentSpec = tuple[tuple[str, ...], dict[str, Any]]
H = TypeVar('H', bound=Callable[..., Any])


@dataclass(frozen=True)
class Command:
    name: str
    help: str | None
    arguments: tuple[ArgumentSpec, ...]
    handler: Handler


REGISTRY: list[Command] = []


def argument(*flags: str, **options: Any) -> Callable[[H], H]:
    """Attach one argparse argument to the decorated handler."""
    def attach(handler: H) -> H:
        # Decorators apply bottom-up; inserting first keeps the reading order.
        vars(handler).setdefault('_cli_arguments', []).insert(0, (flags, options))
        return handler
    return attach


def command(name: str, *, help: str | None = None) -> Callable[[Handler], Handler]:
    """Register the decorated `(args, console) -> (result, exit_code)` handler."""
    def register(handler: Handler) -> Handler:
        if any(existing.name == name for existing in REGISTRY):
            raise ValueError(f'command already registered: {name}')
        REGISTRY.append(Command(name, help, tuple(getattr(handler, '_cli_arguments', ())), handler))
        return handler
    return register


def add_commands(subcommands: argparse._SubParsersAction[Any]) -> None:
    """Add every registered command to an argparse subparsers action."""
    for entry in REGISTRY:
        parser = subcommands.add_parser(entry.name, help=entry.help)
        for flags, options in entry.arguments:
            parser.add_argument(*flags, **options)
        parser.set_defaults(handler=entry.handler)
