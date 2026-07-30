#!/usr/bin/env python3
"""Generate the shortcut contract controlled-vocabulary reference."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "contract" / "shortcut-schema.json"
OUTPUT = ROOT / "contract" / "shortcut-vocabulary.md"
VOCABULARIES = (
    "inputKind",
    "auditStatus",
    "mappingRole",
    "implementationType",
    "mappingClass",
    "availability",
    "mappingStatus",
    "evidenceKind",
    "evidenceClaim",
    "evidenceResult",
)


def render(schema: dict) -> str:
    lines = ["# Shortcut Contract Vocabulary", ""]
    lines.append("Generated from `contract/shortcut-schema.json`; do not edit manually.")
    lines.append("")
    lines.append("Regenerate with `uv run python tools/generate_shortcut_vocabulary.py --write`.")
    lines.append("")
    for name in VOCABULARIES:
        try:
            vocabulary = schema["$defs"][name]
        except KeyError as exc:
            raise ValueError(f"schema is missing documented vocabulary {name!r}") from exc
        if not vocabulary.get("description") or not vocabulary.get("oneOf"):
            raise ValueError(f"vocabulary {name!r} needs a description and oneOf values")
        lines.extend((f"## {vocabulary['title']}", "", vocabulary["description"], ""))
        for option in vocabulary["oneOf"]:
            if "const" not in option or not option.get("description"):
                raise ValueError(f"vocabulary {name!r} has an undocumented value")
            lines.append(f"- `{option['const']}`: {option['description']}")
        lines.append("")
    lines.extend(
        (
            "## Evidence Compatibility",
            "",
            "The schema permits only these kind, claim, and result combinations:",
            "",
            "- `Action registration`: `Target exists` or `Building block exists`, `Confirmed`.",
            "- `Callback implementation`: `Behavior candidate`, `Candidate`.",
            "- `Lua API`: `Lua feasible`, `Candidate`.",
            "- `Default binding` and `Profile binding`: `Binding exists`, `Confirmed`.",
            "- `Ardour manual`: `Behavior candidate`, `Candidate`.",
            "- `Manual test` and `E2E test`: `Behavior verified`, `Confirmed`.",
            "- `Capability audit`: `UI only` or `Capability missing`, `Candidate`.",
            "- `Key conflict`: `Key conflict`, `Conflict`.",
            "",
        )
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--write", action="store_true")
    args = parser.parse_args()
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    text = render(schema)
    if args.check and (not OUTPUT.exists() or OUTPUT.read_text(encoding="utf-8") != text):
        print("Shortcut vocabulary is not current: contract/shortcut-vocabulary.md")
        return 1
    if args.write:
        OUTPUT.write_text(text, encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
