#!/usr/bin/env python3
"""Canonically format shortcut contract JSON documents."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "contract"


def reject_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=reject_duplicates)


def ordered(data: dict) -> dict:
    if "documentType" not in data:
        return data
    if data["documentType"] == "shortcut-sources":
        data["sections"].sort(key=lambda section: section["number"])
        for section in data["sections"]:
            section["shortcuts"].sort(key=lambda shortcut: shortcut["sourceId"])
    else:
        data["shortcuts"].sort(key=lambda shortcut: shortcut["sourceId"])
        for shortcut in data["shortcuts"]:
            role_order = {"Preferred": 0, "Current fallback": 1, "Alternative": 2}
            shortcut["mappings"].sort(
                key=lambda mapping: (
                    role_order[mapping["role"]],
                    mapping.get("context", ""),
                    mapping.get("actionTarget", ""),
                )
            )
            for mapping in shortcut["mappings"]:
                mapping["evidence"].sort(
                    key=lambda evidence: (evidence["kind"], evidence["reference"])
                )
    return data


def paths() -> list[Path]:
    return [
        CONTRACT / "shortcut-schema.json",
        CONTRACT / "ableton-shortcuts.json",
        *sorted((CONTRACT / "shortcut-mappings").glob("*.json")),
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--write", action="store_true")
    args = parser.parse_args()
    changed = []
    for path in paths():
        text = json.dumps(ordered(load(path)), indent=2, ensure_ascii=True) + "\n"
        if path.read_text(encoding="utf-8") != text:
            changed.append(path)
            if args.write:
                path.write_text(text, encoding="utf-8", newline="\n")
    if changed and args.check:
        print("Shortcut JSON is not canonical:")
        print("\n".join(str(path.relative_to(ROOT)) for path in changed))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
