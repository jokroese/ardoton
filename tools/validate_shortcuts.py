#!/usr/bin/env python3
"""Validate the Ableton shortcut inventory and Ardour mapping contract."""

from __future__ import annotations

import argparse
import json
import sys
import tomllib
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "contract"


def reject_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=reject_duplicates)


def mapping_paths(mapping_dir: Path) -> list[Path]:
    return sorted(mapping_dir.glob("*.json"))


def documents(source_path: Path, mapping_dir: Path) -> tuple[dict, list[tuple[Path, dict]]]:
    return load_json(source_path), [(path, load_json(path)) for path in mapping_paths(mapping_dir)]


def validate_contract(
    source_path: Path = CONTRACT / "ableton-shortcuts.json",
    mapping_dir: Path = CONTRACT / "shortcut-mappings",
    keymap_path: Path | None = None,
) -> list[str]:
    """Validate JSON schemas and relationships, returning human-readable errors."""
    errors: list[str] = []
    try:
        schema = load_json(source_path.parent / "shortcut-schema.json")
        Draft202012Validator.check_schema(schema)
        sources, mapping_docs = documents(source_path, mapping_dir)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return [str(exc)]
    validator = Draft202012Validator(schema)
    for path, document in [(source_path, sources), *mapping_docs]:
        for error in sorted(validator.iter_errors(document), key=lambda item: list(item.path)):
            location = "/".join(str(part) for part in error.absolute_path)
            errors.append(f"{path}: {location}: {error.message}")

    source_by_id: dict[str, tuple[dict, dict]] = {}
    for section in sources.get("sections", []):
        for source in section.get("shortcuts", []):
            source_id = source.get("sourceId", "")
            if source_id in source_by_id:
                errors.append(f"duplicate source ID {source_id!r}")
            source_by_id[source_id] = (section, source)

    seen_sources: set[str] = set()
    tuples: set[tuple[str, str, str, str]] = set()
    mappings_by_source: dict[str, list[dict]] = {}
    for path, document in mapping_docs:
        section = document.get("section", {})
        for record in document.get("shortcuts", []):
            source_id = record.get("sourceId", "")
            if source_id in seen_sources:
                errors.append(f"duplicate mapping source ID {source_id!r}")
            seen_sources.add(source_id)
            source_section, source = source_by_id.get(source_id, ({}, {}))
            if not source:
                errors.append(f"{path}: unknown source ID {source_id!r}")
            elif section.get("number") != source_section.get("number") or section.get(
                "title"
            ) != source_section.get("title"):
                errors.append(f"{path}: source ID {source_id!r} is in the wrong section")
            mappings = record.get("mappings", [])
            mappings_by_source[source_id] = mappings
            if record.get("auditStatus") == "Needs audit" and mappings:
                errors.append(f"source ID {source_id!r}: Needs audit must have no mappings")
            if record.get("auditStatus") == "Partially assessed":
                preferred = sum(item.get("role") == "Preferred" for item in mappings)
                if not mappings or preferred:
                    errors.append(
                        f"source ID {source_id!r}: partially assessed source requires mappings "
                        "without a Preferred mapping"
                    )
            if record.get("auditStatus") == "Assessed":
                preferred = sum(item.get("role") == "Preferred" for item in mappings)
                if preferred != 1:
                    errors.append(
                        f"source ID {source_id!r}: assessed source requires one Preferred mapping"
                    )
            for mapping in mappings:
                tuple_value = (
                    source_id,
                    mapping.get("role", ""),
                    mapping.get("context", ""),
                    mapping.get("actionTarget", ""),
                )
                if tuple_value in tuples:
                    errors.append(f"duplicate mapping tuple {tuple_value!r}")
                tuples.add(tuple_value)
                evidence = mapping.get("evidence", [])
                if mapping.get("actionTarget", "").endswith(" (new)") and any(
                    item.get("claim") == "Target exists" for item in evidence
                ):
                    errors.append(
                        f"source ID {source_id!r}: new target requires "
                        "Building block exists evidence"
                    )
                if source.get("inputKind") in {"Keyboard", "Keyboard hold"} and not mapping.get(
                    "keyToken"
                ):
                    errors.append(f"source ID {source_id!r}: keyboard mapping requires keyToken")
                if mapping.get("mappingClass") == "Exact" and not any(
                    item.get("kind") in {"Callback implementation", "Manual test", "E2E test"}
                    and item.get("claim") in {"Behavior verified", "Behavior candidate"}
                    for item in evidence
                ):
                    errors.append(f"source ID {source_id!r}: Exact requires behavior evidence")
                if mapping.get("availability") == "Missing" and not any(
                    item.get("kind") == "Capability audit"
                    and item.get("claim") == "Capability missing"
                    for item in evidence
                ):
                    errors.append(
                        f"source ID {source_id!r}: Missing requires capability audit evidence"
                    )
                if (
                    mapping.get("implementationType") in {"Profile keybinding", "Profile Lua"}
                    and mapping.get("status") == "Implemented"
                    and not any(
                        item.get("kind") == "Profile binding"
                        and item.get("claim") == "Binding exists"
                        and item.get("result") == "Confirmed"
                        for item in evidence
                    )
                ):
                    errors.append(
                        f"source ID {source_id!r}: implemented profile mapping requires "
                        "profile binding evidence"
                    )
                if mapping.get("implementationType") == "Profile Lua" and not any(
                    (item.get("kind") == "Lua API" and item.get("claim") == "Lua feasible")
                    or (
                        item.get("kind") == "Action registration"
                        and item.get("claim") == "Building block exists"
                    )
                    for item in evidence
                ):
                    errors.append(
                        f"source ID {source_id!r}: Profile Lua requires Lua API or action evidence"
                    )
                if mapping.get("implementationType") == "Profile keybinding" and source.get(
                    "inputKind"
                ) not in {"Keyboard", "Keyboard hold"}:
                    errors.append(
                        f"source ID {source_id!r}: Profile keybinding requires a keyboard source"
                    )
    for source_id in sorted(set(source_by_id) - seen_sources):
        errors.append(f"source ID {source_id!r}: has no mapping")

    if keymap_path is not None:
        keymap: dict[tuple[str, str], list[str]] = defaultdict(list)
        for group in ET.parse(keymap_path).getroot().findall("Bindings"):
            for binding in group.findall("./Press/Binding"):
                keymap[(group.get("name") or "", binding.get("key") or "")].append(
                    binding.get("action") or ""
                )
        for source_id, mappings in mappings_by_source.items():
            for mapping in mappings:
                pair = (mapping.get("context", ""), mapping.get("keyToken", ""))
                if (
                    mapping.get("role") == "Preferred"
                    and pair[1]
                    and any(
                        action != mapping.get("actionTarget", "") for action in keymap.get(pair, [])
                    )
                    and not any(
                        item.get("kind") == "Key conflict" and item.get("result") == "Conflict"
                        for item in mapping.get("evidence", [])
                    )
                ):
                    errors.append(f"source ID {source_id!r}: key token collision for {pair!r}")
                if (
                    mapping.get("implementationType") in {"Profile keybinding", "Profile Lua"}
                    and mapping.get("status") == "Implemented"
                    and mapping.get("keyToken")
                    and mapping.get("actionTarget") not in keymap.get(pair, [])
                ):
                    errors.append(
                        f"source ID {source_id!r}: implemented profile mapping is absent "
                        "from keymap"
                    )
    return errors


def validate_expectations(expectations_path: Path, mapping_dir: Path) -> list[str]:
    """Ensure expectation source IDs resolve to implemented profile mappings."""
    errors: list[str] = []
    _, mapping_docs = documents(CONTRACT / "ableton-shortcuts.json", mapping_dir)
    mappings = {
        record["sourceId"]: record["mappings"]
        for _, document in mapping_docs
        for record in document["shortcuts"]
    }
    data = tomllib.loads(expectations_path.read_text(encoding="utf-8"))
    for section in ("binding", "exclusive"):
        for index, row in enumerate(data.get(section, []), 1):
            source_id = row.get("source_id", "")
            candidates = mappings.get(source_id, [])
            if not candidates:
                errors.append(f"expectations {section} {index}: unknown source_id {source_id!r}")
                continue
            profile_candidates = [
                item
                for item in candidates
                if item.get("implementationType") in {"Profile keybinding", "Profile Lua"}
                and item.get("status") == "Implemented"
            ]
            if not profile_candidates:
                errors.append(
                    f"expectations {section} {index}: source_id {source_id!r} requires "
                    "an implemented profile-bound mapping"
                )
            elif section == "binding" and not any(
                item.get("context") == row.get("context")
                and item.get("keyToken") == row.get("key")
                and item.get("actionTarget") == row.get("action")
                for item in profile_candidates
            ):
                errors.append(
                    f"expectations {section} {index}: source_id {source_id!r} does not "
                    "match its implemented profile mapping"
                )
    return errors


def section_numbers(section_number: str | list[str] | None) -> set[str] | None:
    if section_number is None:
        return None
    return {section_number} if isinstance(section_number, str) else set(section_number)


def report(
    source_path: Path, mapping_dir: Path, section_number: str | list[str] | None = None
) -> str:
    sources, mapping_docs = documents(source_path, mapping_dir)
    selected_sections = section_numbers(section_number)
    source_records = [
        (section, shortcut)
        for section in sources["sections"]
        for shortcut in section["shortcuts"]
        if selected_sections is None or section["number"] in selected_sections
    ]
    mapping_records = [
        record
        for _, document in mapping_docs
        if selected_sections is None or document["section"]["number"] in selected_sections
        for record in document["shortcuts"]
    ]
    mapping_status_counts = Counter(
        mapping["status"] for record in mapping_records for mapping in record["mappings"]
    )
    audit_status_counts = Counter(record["auditStatus"] for record in mapping_records)
    implementation_counts = Counter(
        mapping["implementationType"]
        for record in mapping_records
        for mapping in record["mappings"]
    )
    lines = ["Audit status:"]
    lines.extend(
        f"  {status}: {audit_status_counts[status]}" for status in sorted(audit_status_counts)
    )
    lines.append("Source input kinds:")
    lines.extend(
        f"  {kind}: {count}"
        for kind, count in sorted(
            Counter(source["inputKind"] for _, source in source_records).items()
        )
    )
    lines.append("Implementation types:")
    lines.extend(
        f"  {implementation_type}: {count}"
        for implementation_type, count in sorted(implementation_counts.items())
    )
    lines.append("Mapping statuses:")
    lines.extend(f"  {status}: {count}" for status, count in sorted(mapping_status_counts.items()))
    lines.append("Section progress:")
    lines.append("  Section | Sources | Needs audit | Partial | Assessed | Mappings")
    source_by_section = Counter(section["number"] for section, _ in source_records)
    records_by_section: dict[str, list[dict]] = defaultdict(list)
    for record in mapping_records:
        records_by_section[record["sourceId"][1:3]].append(record)
    for number in sorted(source_by_section):
        records = records_by_section[number]
        statuses = Counter(record["auditStatus"] for record in records)
        mapping_count = sum(len(record["mappings"]) for record in records)
        lines.append(
            "  "
            f"{number} | {source_by_section[number]} | {statuses['Needs audit']} | "
            f"{statuses['Partially assessed']} | {statuses['Assessed']} | {mapping_count}"
        )
    return "\n".join(lines)


def section_report(source_path: Path, mapping_dir: Path, section_number: str) -> str:
    """Render a source-to-mapping report for one shortcut section."""
    sources, mapping_docs = documents(source_path, mapping_dir)
    mapping_by_source = {
        record["sourceId"]: record
        for _, document in mapping_docs
        if document["section"]["number"] == section_number
        for record in document["shortcuts"]
    }
    source_records = sorted(
        (
            source
            for section in sources["sections"]
            if section["number"] == section_number
            for source in section["shortcuts"]
        ),
        key=lambda source: source["sourceId"],
    )
    role_order = {"Preferred": 0, "Current fallback": 1, "Alternative": 2}
    lines = [f"Section {section_number} joined report:"]
    for source in source_records:
        record = mapping_by_source[source["sourceId"]]
        lines.append(
            " | ".join(
                (
                    source["sourceId"],
                    source["action"],
                    source["inputKind"],
                    source["context"],
                    record["auditStatus"],
                )
            )
        )
        for mapping in sorted(
            record["mappings"],
            key=lambda item: (
                role_order[item["role"]],
                item.get("context", ""),
                item.get("actionTarget", ""),
            ),
        ):
            lines.append(
                "  Mapping | "
                + " | ".join(
                    (
                        mapping["role"],
                        mapping.get("implementationType", ""),
                        mapping.get("mappingClass", ""),
                        mapping["status"],
                        mapping.get("actionTarget", ""),
                    )
                )
            )
            for evidence in sorted(
                mapping["evidence"], key=lambda item: (item["kind"], item["reference"])
            ):
                lines.append(
                    "    Evidence | "
                    + " | ".join(
                        (
                            evidence["kind"],
                            evidence["claim"],
                            evidence["result"],
                            evidence["reference"],
                        )
                    )
                )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", action="store_true")
    parser.add_argument("--section", metavar="NN", action="append")
    args = parser.parse_args()
    source_path = CONTRACT / "ableton-shortcuts.json"
    mapping_dir = CONTRACT / "shortcut-mappings"
    errors = validate_contract(
        source_path, mapping_dir, ROOT / "profile" / "keybindings" / "macos" / "ardour.keys"
    )
    errors.extend(validate_expectations(ROOT / "tests" / "expectations.toml", mapping_dir))
    if errors:
        print("\n".join(f"error: {error}" for error in errors), file=sys.stderr)
        return 1
    sources, _ = documents(source_path, mapping_dir)
    known_sections = {section["number"] for section in sources["sections"]}
    unknown_sections = set(args.section or []) - known_sections
    if unknown_sections:
        parser.error(f"unknown section(s): {', '.join(sorted(unknown_sections))}")
    print(f"Validated {sum(len(section['shortcuts']) for section in sources['sections'])} sources.")
    if args.report:
        print(report(source_path, mapping_dir, args.section))
    if args.section:
        for section in args.section:
            print(section_report(source_path, mapping_dir, section))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
