# Ardourton

Ardourton is a project that adapts Ardour to feel familiar to Ableton Live users.

It currently supports stock Ardour 9.7 on macOS.

## Development

Use the pinned Python and uv versions to create the local environment:

```bash
uv sync --locked
uv run pre-commit install
```

Run the standard non-GUI gate:

```bash
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest -m "not e2e and not requires_ardour"
```

Run the full local release gate, including installer validation and Ardour GUI tests:

```bash
uv run pytest -m "not e2e"
uv run pytest -m e2e
```

E2E tests require Ardour 9.7 at `/Applications/Ardour9.app` and macOS Accessibility
permission for the test process. They isolate Ardour's configuration and must not be run
against a live Ardour session.

## Contract tools

```bash
uv run python tools/format_shortcuts.py --check
uv run python tools/validate_shortcuts.py --report
```

Use `uv run python tools/format_shortcuts.py --write` to canonicalize contract JSON.

## Dependency updates

```bash
uv lock --upgrade
uv sync
```

Commit the updated `uv.lock` with dependency changes.
