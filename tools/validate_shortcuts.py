#!/usr/bin/env python3
"""Validate the Ableton shortcut inventory and its Ardour mapping contract."""

from __future__ import annotations

import argparse
import csv
import re
import sys
import tomllib
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

SOURCE_ID_PATTERN = re.compile(r"S[0-9]{2}-[0-9]{2}$")
MAPPING_ID_PATTERN = re.compile(r"M[0-9]{3}$")
EVIDENCE_ID_PATTERN = re.compile(r"E[0-9]{3}$")

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
    "Mapping role",
    "Ardour context",
    "Proposed macOS",
    "Ardour key token",
    "Ardour action target",
    "Implementation type",
    "Mapping class",
    "Availability",
    "Conflict / implementation note",
    "Status",
)
EVIDENCE_FIELDS = ("Evidence ID", "Mapping ID", "Evidence kind", "Claim", "Reference", "Result")

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
        "Lua accessible",
        "UI only",
        "Missing",
        "Unknown",
    },
    "Mapping role": {"Preferred", "Current fallback", "Alternative", "Placeholder"},
    "Status": {"Needs audit", "Proposed", "Implemented", "Blocked", "Rejected"},
}
EVIDENCE_VALUES = {
    "Evidence kind": {
        "Action registration",
        "Callback implementation",
        "Lua API",
        "Default binding",
        "Profile binding",
        "Ardour manual",
        "Manual test",
        "E2E test",
        "Capability audit",
        "Key conflict",
    },
    "Claim": {
        "Target exists",
        "Behavior candidate",
        "Binding exists",
        "Lua feasible",
        "UI only",
        "Capability missing",
        "Key conflict",
        "Behavior verified",
    },
    "Result": {"Confirmed", "Candidate", "Conflict", "Unverified"},
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


def validate_contract(
    source_path: Path,
    mapping_path: Path,
    evidence_path: Path | None = None,
    keymap_path: Path | None = None,
) -> list[str]:
    """Validate contract CSVs and return human-readable errors."""
    sources, errors = read_csv(source_path, SOURCE_FIELDS)
    mappings, mapping_errors = read_csv(mapping_path, MAPPING_FIELDS)
    errors.extend(mapping_errors)
    if evidence_path is None:
        evidence_path = mapping_path.with_name("shortcut-evidence.csv")
    evidence, evidence_errors = (
        read_csv(evidence_path, EVIDENCE_FIELDS) if evidence_path.exists() else ([], [])
    )
    errors.extend(evidence_errors)

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

        role = row.get("Mapping role", "")
        if role == "Placeholder":
            if status != "Needs audit":
                errors.append(f"mapping line {line}: Placeholder requires Status 'Needs audit'")
            if any(row.get(field) for field in MAPPING_FIELDS[3:-1]):
                errors.append(
                    f"mapping line {line}: Placeholder must contain no implementation fields"
                )
        if role == "Current fallback":
            if status != "Implemented":
                errors.append(
                    f"mapping line {line}: Current fallback requires Status 'Implemented'"
                )
            if row.get("Mapping class") not in {"Similar", "Needs audit"}:
                errors.append(
                    f"mapping line {line}: Current fallback requires Mapping class "
                    "Similar or Needs audit"
                )
        if status in {"Proposed", "Implemented"}:
            for field in (
                "Ardour context",
                "Ardour action target",
                "Implementation type",
                "Mapping class",
                "Availability",
            ):
                require(errors, row, line, field, status)
            if role in {"", "Placeholder"}:
                errors.append(
                    f"mapping line {line}: {status} requires a non-placeholder Mapping role"
                )

    evidence_ids: set[str] = set()
    evidence_by_mapping: dict[str, list[dict[str, str]]] = {}
    for line, row in enumerate(evidence, start=2):
        evidence_id = row.get("Evidence ID", "")
        if not EVIDENCE_ID_PATTERN.fullmatch(evidence_id):
            errors.append(f"evidence line {line}: invalid Evidence ID {evidence_id!r}")
        if evidence_id in evidence_ids:
            errors.append(f"evidence line {line}: duplicate Evidence ID {evidence_id!r}")
        evidence_ids.add(evidence_id)
        if row.get("Mapping ID") not in mapping_ids:
            errors.append(f"evidence line {line}: unknown Mapping ID {row.get('Mapping ID', '')!r}")
        evidence_by_mapping.setdefault(row.get("Mapping ID", ""), []).append(row)
        for field, allowed in EVIDENCE_VALUES.items():
            if row.get(field) not in allowed:
                errors.append(f"evidence line {line}: invalid {field} {row.get(field, '')!r}")
    for line, row in enumerate(mappings, start=2):
        mapping_evidence = evidence_by_mapping.get(row.get("Mapping ID", ""), [])
        if row.get("Mapping role") != "Placeholder" and not mapping_evidence:
            errors.append(f"mapping line {line}: non-placeholder requires evidence")
        if row.get("Mapping class") == "Exact" and not any(
            item.get("Evidence kind") in {"Callback implementation", "Manual test", "E2E test"}
            and item.get("Claim") in {"Behavior verified", "Behavior candidate"}
            for item in mapping_evidence
        ):
            errors.append(f"mapping line {line}: Exact requires behavior evidence")
        if row.get("Availability") == "Missing" and not any(
            item.get("Evidence kind") == "Capability audit"
            and item.get("Claim") == "Capability missing"
            for item in mapping_evidence
        ):
            errors.append(f"mapping line {line}: Missing requires capability audit evidence")
        if (
            row.get("Implementation type") in {"Profile keybinding", "Profile Lua"}
            and row.get("Status") == "Implemented"
            and not any(
                item.get("Evidence kind") == "Profile binding"
                and item.get("Claim") == "Binding exists"
                and item.get("Result") == "Confirmed"
                for item in mapping_evidence
            )
        ):
            errors.append(
                f"mapping line {line}: implemented profile mapping requires "
                "profile binding evidence"
            )
    if keymap_path is not None:
        keymap = {
            (group.get("name") or "", binding.get("key") or ""): binding.get("action") or ""
            for group in ET.parse(keymap_path).getroot().findall("Bindings")
            for binding in group.findall("./Press/Binding")
        }
        for line, row in enumerate(mappings, start=2):
            pair = (row.get("Ardour context", ""), row.get("Ardour key token", ""))
            if (
                row.get("Mapping role") == "Preferred"
                and row.get("Implementation type") == "Profile keybinding"
                and pair[1]
                and keymap.get(pair) not in {None, row.get("Ardour action target", "")}
                and not any(
                    item.get("Evidence kind") == "Key conflict" and item.get("Result") == "Conflict"
                    for item in evidence_by_mapping.get(row.get("Mapping ID", ""), [])
                )
            ):
                errors.append(f"mapping line {line}: key token collision for {pair!r}")
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


def report(source_path: Path, mapping_path: Path, evidence_path: Path) -> str:
    sources, _ = read_csv(source_path, SOURCE_FIELDS)
    mappings, _ = read_csv(mapping_path, MAPPING_FIELDS)
    evidence, _ = read_csv(evidence_path, EVIDENCE_FIELDS)
    source_counts = Counter(row.get("Input kind", "") for row in sources)
    status_counts = Counter(row.get("Status", "") for row in mappings)
    lines = ["Source input kinds:"]
    lines.extend(f"  {kind}: {count}" for kind, count in sorted(source_counts.items()))
    lines.append("Mapping statuses:")
    lines.extend(f"  {status}: {count}" for status, count in sorted(status_counts.items()))
    lines.append(f"Evidence records: {len(evidence)}")
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
    evidence_path = root / "contract" / "shortcut-evidence.csv"
    keymap_path = root / "profile" / "keybindings" / "macos" / "ardour.keys"
    errors = validate_contract(source_path, mapping_path, evidence_path, keymap_path)
    errors.extend(validate_expectations(root / "tests" / "expectations.toml", mapping_path))
    if errors:
        print("\n".join(f"error: {error}" for error in errors), file=sys.stderr)
        return 1
    source_count = len(read_csv(source_path, SOURCE_FIELDS)[0])
    mapping_count = len(read_csv(mapping_path, MAPPING_FIELDS)[0])
    print(f"Validated {source_count} sources and {mapping_count} mappings.")
    if args.report:
        print(report(source_path, mapping_path, evidence_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
