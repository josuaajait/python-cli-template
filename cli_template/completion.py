"""Tab-completion scripts generated from the argument parser.

    python-cli --completion powershell | Out-String | Invoke-Expression
    eval "$(python-cli --completion bash)"
    eval "$(python-cli --completion zsh)"

Subcommands and their options are read from the parser when the script is
printed, so new @command handlers are completed without further changes.
"""
import argparse
import re
import sys
from typing import Any, NoReturn


SHELLS = ('powershell', 'bash', 'zsh')


def completion_spec(parser: argparse.ArgumentParser) -> tuple[list[str], dict[str, list[str]]]:
    """Top-level words (commands and options) and each command's options."""
    top: list[str] = []
    commands: dict[str, list[str]] = {}
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            for name, subparser in action.choices.items():
                commands[name] = _options(subparser)
        else:
            top.extend(action.option_strings)
    return [*commands, *sorted(set(top), key=top.index)], commands


def _options(parser: argparse.ArgumentParser) -> list[str]:
    words = [flag for action in parser._actions for flag in action.option_strings]
    return sorted(set(words), key=words.index)


def render(shell: str, prog: str, parser: argparse.ArgumentParser) -> str:
    top, commands = completion_spec(parser)
    if shell == 'powershell':
        return _powershell(prog, top, commands)
    script = _bash(prog, top, commands)
    if shell == 'zsh':
        return 'autoload -U +X compinit && compinit\nautoload -U +X bashcompinit && bashcompinit\n' + script
    return script


def _bash(prog: str, top: list[str], commands: dict[str, list[str]]) -> str:
    function = '_' + re.sub(r'\W', '_', prog) + '_complete'
    cases = ''.join(f'    {name}) words="{" ".join(options)}" ;;\n' for name, options in commands.items())
    return (
        f'{function}() {{\n'
        '  local cur="${COMP_WORDS[COMP_CWORD]}" command="" word words\n'
        '  for word in "${COMP_WORDS[@]:1:COMP_CWORD-1}"; do\n'
        f'    case "$word" in {"|".join(commands)}) command="$word"; break ;; esac\n'
        '  done\n'
        '  case "$command" in\n'
        f'{cases}'
        f'    *) words="{" ".join(top)}" ;;\n'
        '  esac\n'
        '  COMPREPLY=($(compgen -W "$words" -- "$cur"))\n'
        '}\n'
        f'complete -o default -F {function} {prog}\n'
    )


def _powershell(prog: str, top: list[str], commands: dict[str, list[str]]) -> str:
    def array(words: list[str]) -> str:
        return '@(' + ', '.join(f"'{word}'" for word in words) + ')'

    table = ''.join(f"        '{name}' = {array(options)}\n" for name, options in commands.items())
    return (
        f"Register-ArgumentCompleter -Native -CommandName '{prog}' -ScriptBlock {{\n"
        '    param($wordToComplete, $commandAst, $cursorPosition)\n'
        '    $commands = @{\n'
        f'{table}'
        '    }\n'
        f'    $top = {array(top)}\n'
        '    $typed = @($commandAst.CommandElements | Select-Object -Skip 1 | ForEach-Object { $_.ToString() })\n'
        '    $command = $typed | Where-Object { $commands.ContainsKey($_) -and $_ -ne $wordToComplete } |\n'
        '        Select-Object -First 1\n'
        '    $candidates = if ($command) { $commands[$command] } else { $top }\n'
        '    $candidates | Where-Object { $_ -like "$wordToComplete*" } | ForEach-Object {\n'
        "        [System.Management.Automation.CompletionResult]::new($_, $_, 'ParameterValue', $_)\n"
        '    }\n'
        '}\n'
    )


class CompletionAction(argparse.Action):
    """`--completion SHELL`: print the script and exit, like --version."""

    def __init__(self, option_strings: list[str], dest: str, **kwargs: Any) -> None:
        super().__init__(option_strings, dest, nargs=1, choices=SHELLS, metavar='SHELL', **kwargs)

    def __call__(self, parser: argparse.ArgumentParser, namespace: argparse.Namespace,
                 values: Any, option_string: str | None = None) -> NoReturn:
        sys.stdout.write(render(values[0], parser.prog, parser))
        sys.stdout.flush()
        parser.exit()
