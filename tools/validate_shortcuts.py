#!/usr/bin/env python3
"""Validate the Ableton shortcut inventory and its Ardour mapping contract."""

from __future__ import annotations

import argparse
import csv
import re
import sys
import tomllib
from collections import Counter
from pathlib import Path

SOURCE_ID_PATTERN = re.compile(r"S[0-9]{2}-[0-9]{2}$")
MAPPING_ID_PATTERN = re.compile(r"M[0-9]{3}$")

SOURCE_FIELDS = (
    "ID",
    "Action",
    "Input kind",
    "Live macOS",
    "Context",
    "Live manual section",
)
MAPPING_FIELDS = (
    "Mapping ID",
    "Ableton shortcut ID",
    "Ardour context",
    "Proposed macOS",
    "Ardour action target",
    "Implementation type",
    "Mapping class",
    "Availability",
    "Evidence type",
    "Evidence reference",
    "Static verification",
    "Behavior verification",
    "Conflict / implementation note",
    "Status",
)

INPUT_KINDS = {
    "Keyboard",
    "Keyboard hold",
    "Mouse gesture",
    "Modifier gesture",
    "Accessibility command",
}
CONTROLLED_VALUES = {
    "Implementation type": {
        "Profile keybinding",
        "Profile Lua",
        "None",
        "Ardour action patch",
        "Ardour input patch",
        "Ardour UI patch",
        "Ardour engine patch",
        "Undetermined",
    },
    "Mapping class": {"Exact", "Similar", "No equivalent", "Needs audit"},
    "Availability": {
        "Profile bound",
        "Native bound",
        "Native unbound",
        "UI only",
        "Missing",
        "Unknown",
    },
    "Evidence type": {
        "Profile keymap",
        "Ardour defaults",
        "Ardour manual",
        "Ardour action list",
        "Manual test",
        "None",
    },
    "Static verification": {"Not applicable", "Not run", "Passed", "Failed"},
    "Behavior verification": {"Not run", "Manual passed", "E2E passed", "Failed", "Blocked"},
    "Status": {
        "Implemented",
        "Implemented with divergence",
        "Static verified",
        "Proposed",
        "Needs audit",
        "Blocked",
        "No equivalent",
    },
}


def read_csv(path: Path, fields: tuple[str, ...]) -> tuple[list[dict[str, str]], list[str]]:
    """Return normalized CSV rows and errors for missing contract columns."""
    with path.open(newline="", encoding="utf-8") as source:
        reader = csv.DictReader(source)
        headers = reader.fieldnames or []
        errors = [f"{path}: missing column {field!r}" for field in fields if field not in headers]
        return [
            {key: (value or "").strip() for key, value in row.items() if key} for row in reader
        ], errors


def require(errors: list[str], row: dict[str, str], line: int, field: str, status: str) -> None:
    if not row.get(field):
        errors.append(f"mapping line {line}: {status} requires {field}")


def validate_contract(source_path: Path, mapping_path: Path) -> list[str]:
    """Validate contract CSVs and return human-readable errors."""
    sources, errors = read_csv(source_path, SOURCE_FIELDS)
    mappings, mapping_errors = read_csv(mapping_path, MAPPING_FIELDS)
    errors.extend(mapping_errors)

    source_ids: set[str] = set()
    source_kinds: dict[str, str] = {}
    for line, row in enumerate(sources, start=2):
        source_id = row.get("ID", "")
        if not SOURCE_ID_PATTERN.fullmatch(source_id):
            errors.append(f"source line {line}: invalid ID {source_id!r}")
        if source_id in source_ids:
            errors.append(f"source line {line}: duplicate ID {source_id!r}")
        source_ids.add(source_id)
        source_kinds.setdefault(source_id, row.get("Input kind", ""))
        if row.get("Input kind") not in INPUT_KINDS:
            errors.append(f"source line {line}: invalid Input kind {row.get('Input kind', '')!r}")
        for field in ("Action", "Live macOS", "Context", "Live manual section"):
            if not row.get(field):
                errors.append(f"source line {line}: missing {field}")

    mapping_ids: set[str] = set()
    mapped_source_ids: set[str] = set()
    mapping_tuples: set[tuple[str, str, str]] = set()
    for line, row in enumerate(mappings, start=2):
        mapping_id = row.get("Mapping ID", "")
        source_id = row.get("Ableton shortcut ID", "")
        status = row.get("Status", "")
        if not MAPPING_ID_PATTERN.fullmatch(mapping_id):
            errors.append(f"mapping line {line}: invalid Mapping ID {mapping_id!r}")
        if mapping_id in mapping_ids:
            errors.append(f"mapping line {line}: duplicate Mapping ID {mapping_id!r}")
        mapping_ids.add(mapping_id)
        for field in ("Mapping ID", "Ableton shortcut ID", "Status"):
            if not row.get(field):
                errors.append(f"mapping line {line}: missing {field}")
        if source_id not in source_ids:
            errors.append(f"mapping line {line}: unknown Ableton shortcut ID {source_id!r}")
        else:
            mapped_source_ids.add(source_id)

        for field, allowed in CONTROLLED_VALUES.items():
            value = row.get(field, "")
            if value and value not in allowed:
                errors.append(f"mapping line {line}: invalid {field} {value!r}")

        mapping_tuple = (
            source_id,
            row.get("Ardour context", ""),
            row.get("Ardour action target", ""),
        )
        if all(mapping_tuple):
            if mapping_tuple in mapping_tuples:
                errors.append(f"mapping line {line}: duplicate mapping tuple {mapping_tuple!r}")
            mapping_tuples.add(mapping_tuple)

        if row.get("Implementation type") == "Profile keybinding" and source_kinds.get(
            source_id
        ) not in {
            "Keyboard",
            "Keyboard hold",
        }:
            errors.append(
                f"mapping line {line}: Profile keybinding requires a Keyboard or Keyboard hold "
                "source"
            )

        if status == "Proposed":
            for field in (
                "Ardour action target",
                "Implementation type",
                "Mapping class",
                "Availability",
            ):
                require(errors, row, line, field, status)
        elif status == "No equivalent":
            for field in ("Evidence type", "Evidence reference", "Conflict / implementation note"):
                require(errors, row, line, field, status)
            if row.get("Mapping class") != "No equivalent":
                errors.append(
                    f"mapping line {line}: No equivalent requires Mapping class 'No equivalent'"
                )
            if row.get("Availability") != "Missing":
                errors.append(f"mapping line {line}: No equivalent requires Availability 'Missing'")
        elif status in {"Implemented", "Implemented with divergence"}:
            for field in (
                "Proposed macOS",
                "Ardour context",
                "Ardour action target",
                "Implementation type",
                "Mapping class",
                "Availability",
                "Evidence type",
                "Evidence reference",
            ):
                require(errors, row, line, field, status)
            if row.get("Static verification") != "Passed":
                errors.append(
                    f"mapping line {line}: {status} requires Static verification 'Passed'"
                )
            if row.get("Behavior verification") in {"", "Not run"}:
                errors.append(
                    f"mapping line {line}: {status} requires Behavior verification "
                    "other than 'Not run'"
                )
            if status == "Implemented" and row.get("Mapping class") == "Similar":
                errors.append(
                    f"mapping line {line}: Implemented cannot use Mapping class 'Similar'"
                )
            if status == "Implemented with divergence" and row.get("Mapping class") != "Similar":
                errors.append(
                    f"mapping line {line}: Implemented with divergence requires "
                    "Mapping class 'Similar'"
                )
        elif status == "Static verified":
            for field in (
                "Proposed macOS",
                "Ardour context",
                "Ardour action target",
                "Implementation type",
                "Mapping class",
                "Availability",
                "Evidence type",
                "Evidence reference",
            ):
                require(errors, row, line, field, status)
            if row.get("Static verification") != "Passed":
                errors.append(
                    f"mapping line {line}: Static verified requires Static verification 'Passed'"
                )
        elif status == "Blocked":
            for field in (
                "Implementation type",
                "Evidence type",
                "Evidence reference",
                "Conflict / implementation note",
            ):
                require(errors, row, line, field, status)

    for source_id in sorted(source_ids - mapped_source_ids):
        errors.append(f"source ID {source_id!r}: has no mapping")
    return errors


def validate_expectations(expectations_path: Path, mapping_path: Path) -> list[str]:
    """Validate expectation mappings against profile-bound implementations."""
    mappings, errors = read_csv(mapping_path, MAPPING_FIELDS)
    mapping_by_id = {row.get("Mapping ID", ""): row for row in mappings}
    data = tomllib.loads(expectations_path.read_text(encoding="utf-8"))

    for section in ("binding", "exclusive"):
        for index, row in enumerate(data.get(section, []), start=1):
            mapping_id = row.get("mapping_id", "")
            mapping = mapping_by_id.get(mapping_id)
            prefix = f"expectations {section} {index}"
            if not mapping:
                errors.append(f"{prefix}: unknown mapping_id {mapping_id!r}")
                continue
            if mapping.get("Implementation type") not in {"Profile keybinding", "Profile Lua"}:
                errors.append(
                    f"{prefix}: mapping_id {mapping_id!r} requires Implementation type "
                    "Profile keybinding or Profile Lua"
                )
            if mapping.get("Availability") != "Profile bound":
                errors.append(
                    f"{prefix}: mapping_id {mapping_id!r} requires Availability 'Profile bound'"
                )
    return errors


def report(source_path: Path, mapping_path: Path) -> str:
    sources, _ = read_csv(source_path, SOURCE_FIELDS)
    mappings, _ = read_csv(mapping_path, MAPPING_FIELDS)
    source_counts = Counter(row.get("Input kind", "") for row in sources)
    status_counts = Counter(row.get("Status", "") for row in mappings)
    lines = ["Source input kinds:"]
    lines.extend(f"  {kind}: {count}" for kind, count in sorted(source_counts.items()))
    lines.append("Mapping statuses:")
    lines.extend(f"  {status}: {count}" for status, count in sorted(status_counts.items()))
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--report", action="store_true", help="print source-kind and mapping-status counts"
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    source_path = root / "contract" / "ableton-shortcuts.csv"
    mapping_path = root / "contract" / "shortcuts-map.csv"
    errors = validate_contract(source_path, mapping_path)
    errors.extend(validate_expectations(root / "tests" / "expectations.toml", mapping_path))
    if errors:
        print("\n".join(f"error: {error}" for error in errors), file=sys.stderr)
        return 1
    source_count = len(read_csv(source_path, SOURCE_FIELDS)[0])
    mapping_count = len(read_csv(mapping_path, MAPPING_FIELDS)[0])
    print(f"Validated {source_count} sources and {mapping_count} mappings.")
    if args.report:
        print(report(source_path, mapping_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
