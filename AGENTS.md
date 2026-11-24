# Working on Python CLI Template

Read README.md and docs/design.md. This repository is a generic, standard-library Python CLI starter; keep application-specific integrations in examples or separate projects.

- Python >=3.11; no runtime dependencies without an explicit product reason.
- Brand settings live in cli_template/cli.py; rendering lives in console.py.
- Terminal output is readable by default; redirected stdout is one JSON result. Progress belongs to stderr. Help/version stay text.
- Preserve 0/1/2/130 exit meanings, no-color/dumb-terminal fallback, original JSON values and spinner cleanup before input/results/errors.
- Run `python -m unittest discover -s tests -v`, `python -m cli_template demo --pretty --delay 0` and `python -m cli_template doctor --json` before claiming completion.
- Test behavior, not source spelling. Do not install global software or commit .venv, caches, credentials or generated builds.
