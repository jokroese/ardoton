`shortcut-schema.json` is the executable source of truth for the contract vocabulary and shape.
`shortcut-vocabulary.md` is generated from it and must not be edited manually. `audit-guide.md`
defines the evidence and decision policy.

`ableton-shortcuts.json` is the canonical Ableton Live 12 shortcut inventory. Its provenance is
the `sources.csv` URL reference, and shortcuts remain grouped in manual-section order.
`shortcut-mappings/<section>.json` contains exactly one audit record for each source shortcut.
Mappings and evidence intentionally have no identifiers because `sourceId` is the contract
identifier.

Author workflow:

```bash
uv run python tools/format_shortcuts.py --write
uv run python tools/generate_shortcut_vocabulary.py --write
uv run python tools/format_shortcuts.py --check
uv run python tools/generate_shortcut_vocabulary.py --check
uv run python tools/validate_shortcuts.py --report
uv run python tools/validate_shortcuts.py --section 01
```
