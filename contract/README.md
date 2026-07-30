`ableton-shortcuts.json` is the canonical Ableton Live 12 shortcut inventory. Its source
provenance is the `sources.csv` URL reference, and shortcuts remain grouped in the manual's
section order. `shortcut-mappings/<section>.json` contains exactly one audit record for each
source shortcut in that section. Assessed mappings nest their evidence; mapping and evidence
records intentionally have no identifiers because `sourceId` is the contract identifier.

Validate the contract with `uv run python tools/validate_shortcuts.py --report` or inspect one
joined manual section with `uv run python tools/validate_shortcuts.py --section 01`. Canonically
format the JSON with `uv run python tools/format_shortcuts.py --write` and verify it with
`uv run python tools/format_shortcuts.py --check`.
