# Contributing

Waymark is a small, explicit codebase. These standards keep it maintainable.

## Project layout

```text
src/waymark/
  cli.py        # Typer CLI
  tui.py        # Textual guided interface
  storage.py    # SQLite schema + data access
  imports.py    # explicit file/folder import
  backup.py     # full local backup/restore
  reflection.py, journey.py, retrieval.py, drafting.py, ai.py, ...
tests/          # pytest suite (storage, retrieval, CLI, TUI, imports, backup)
docs/           # this documentation site (MkDocs Material)
```

Keep storage, CLI, TUI, AI runtime, and import logic in separate modules with
explicit boundaries.

## Environment

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev,pdf,docs]"
```

## Standards

- Target Python 3.11+.
- Use dataclasses for plain local data shapes.
- Keep SQLite operations parameterized; store UTC ISO timestamps.
- Avoid global mutable state outside CLI/app wiring.
- Never scan folders, download models, or start background indexing by default.
- Treat model output as a draft; answers must cite sources.

## Verify before committing

All checks must pass:

```bash
ruff check .
mypy src
pytest -q
mkdocs build --strict
python -m build
python -m twine check dist/*
```

CI and release jobs also run a fresh wheel install smoke test:

```bash
python -m venv .wheel-smoke
. .wheel-smoke/bin/activate
python -m pip install dist/*.whl
waymark --version
```

## Working on the docs

```bash
mkdocs serve          # live preview at http://127.0.0.1:8000
```

The CLI reference page renders directly from the Typer app via
`mkdocs-typer2`, so it never drifts — add or change a command in `cli.py` and the
docs update on the next build.

## Cutting a release

Waymark publishes downloadable wheels and source archives through GitHub
Releases. First update `pyproject.toml` and `src/waymark/__init__.py` from the
development version to the exact public version, then commit that release prep.
Push a matching version tag to start the release workflow:

```bash
git commit -am "Prepare release 0.2.0"
git tag v0.2.0
git push origin main
git push origin v0.2.0
```

The tag must match the package version exactly. For example, `v0.2.0` requires:

```toml
version = "0.2.0"
```

and:

```python
__version__ = "0.2.0"
```

The workflow verifies the code, confirms the tag/version match, builds the
package, checks the package metadata, installs the built wheel in a fresh
environment, and uploads `dist/*` to the release.

After the release, bump `main` back to the next development version:

```bash
git commit -am "Start 0.3.0 development"
```

For the first release, the exact commands were:

```bash
git tag v0.1.0
git push origin v0.1.0
```
