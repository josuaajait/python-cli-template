# Contributing

Use Python >=3.11. Run from the repository root:

```sh
python -m pip install -e ".[dev]"
python -m ruff check .
python -m mypy
python -m unittest discover -s tests -v
python -m cli_template demo --pretty --delay 0
python -m cli_template doctor --json
```

Install into a project-local virtual environment, never globally. New functions need type annotations; mypy runs with `disallow_untyped_defs`. Keep coverage at or above the `fail_under` value in `pyproject.toml` (`coverage run -m unittest discover -s tests`, then `coverage combine` and `coverage report`).

Keep command logic in `cli.py` (registered with `@command`/`@argument` from `commands.py`) and presentation in `console.py`. If you change names the template uses, update `scripts/rename_template.py` and its tests. Add a focused behavior test before changing a public command contract. Preserve plain JSON on redirected stdout, optional output flags, useful exit codes and spinner cleanup. Avoid dependencies when the standard library is sufficient.

Tests may control external boundaries such as time delays or input, but should exercise real parsing, handlers and rendering. Do not add generated environments, package artifacts, secrets or logs to commits. Open a pull request with the concrete behavior change and validation performed.
