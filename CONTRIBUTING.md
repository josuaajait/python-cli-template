# Contributing

Use Python >=3.11. Run from the repository root:

```sh
python -m pip install -e .
python -m unittest discover -s tests -v
python -m cli_template demo --pretty --delay 0
python -m cli_template doctor --json
```

Keep command logic in `cli.py` and presentation in `console.py`. Add a focused behavior test before changing a public command contract. Preserve plain JSON on redirected stdout, optional output flags, useful exit codes and spinner cleanup. Avoid dependencies when the standard library is sufficient.

Tests may control external boundaries such as time delays or input, but should exercise real parsing, handlers and rendering. Do not add generated environments, package artifacts, secrets or logs to commits. Open a pull request with the concrete behavior change and validation performed.
