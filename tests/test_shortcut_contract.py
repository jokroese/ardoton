from __future__ import annotations

import csv

from tools.validate_shortcuts import (
    MAPPING_FIELDS,
    SOURCE_FIELDS,
    validate_contract,
    validate_expectations,
)

from support import CONTRACT


def write_csv(path, fields: tuple[str, ...], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def source(source_id: str) -> dict[str, str]:
    return {
        "ID": source_id,
        "Action": "Action",
        "Input kind": "Keyboard",
        "Live macOS": "Cmd+A",
        "Context": "Main window",
        "Live manual section": "1.1 Test",
    }


def mapping(mapping_id: str, source_id: str, **values: str) -> dict[str, str]:
    row = {field: "" for field in MAPPING_FIELDS}
    row.update(
        {"Mapping ID": mapping_id, "Ableton shortcut ID": source_id, "Status": "Needs audit"}
    )
    row.update(values)
    return row


def test_real_shortcut_contract_is_valid() -> None:
    assert (
        validate_contract(CONTRACT / "ableton-shortcuts.csv", CONTRACT / "shortcuts-map.csv") == []
    )


def test_rejects_invalid_controlled_value(tmp_path) -> None:
    sources = tmp_path / "sources.csv"
    mappings = tmp_path / "mappings.csv"
    write_csv(sources, SOURCE_FIELDS, [source("S01-01")])
    write_csv(mappings, MAPPING_FIELDS, [mapping("M001", "S01-01", Availability="Elsewhere")])

    errors = validate_contract(sources, mappings)

    assert "invalid Availability 'Elsewhere'" in errors[0]


def test_accepts_ardour_source_evidence_type(tmp_path) -> None:
    sources = tmp_path / "sources.csv"
    mappings = tmp_path / "mappings.csv"
    write_csv(sources, SOURCE_FIELDS, [source("S01-01")])
    write_csv(
        mappings,
        MAPPING_FIELDS,
        [mapping("M001", "S01-01", **{"Evidence type": "Ardour source"})],
    )

    assert validate_contract(sources, mappings) == []


def test_rejects_source_without_mapping(tmp_path) -> None:
    sources = tmp_path / "sources.csv"
    mappings = tmp_path / "mappings.csv"
    write_csv(sources, SOURCE_FIELDS, [source("S01-01"), source("S01-02")])
    write_csv(mappings, MAPPING_FIELDS, [mapping("M001", "S01-01")])

    errors = validate_contract(sources, mappings)

    assert "source ID 'S01-02': has no mapping" in errors


def test_static_verified_exact_mapping_can_await_behavior_test(tmp_path) -> None:
    sources = tmp_path / "sources.csv"
    mappings = tmp_path / "mappings.csv"
    write_csv(sources, SOURCE_FIELDS, [source("S01-01")])
    write_csv(
        mappings,
        MAPPING_FIELDS,
        [
            mapping(
                "M001",
                "S01-01",
                Status="Static verified",
                **{
                    "Proposed macOS": "Primary-a",
                    "Ardour context": "Global",
                    "Ardour action target": "Action/test",
                    "Implementation type": "Profile keybinding",
                    "Mapping class": "Exact",
                    "Availability": "Profile bound",
                    "Evidence type": "Profile keymap",
                    "Evidence reference": (
                        "profile/keybindings/macos/ardour.keys: Global Primary-a -> Action/test"
                    ),
                    "Static verification": "Passed",
                    "Behavior verification": "Not run",
                },
            )
        ],
    )

    assert validate_contract(sources, mappings) == []


def test_expectation_requires_profile_bound_keybinding_or_lua_mapping(tmp_path) -> None:
    mappings = tmp_path / "mappings.csv"
    expectations = tmp_path / "expectations.toml"
    write_csv(mappings, MAPPING_FIELDS, [mapping("M001", "S01-01")])
    expectations.write_text('[[binding]]\nmapping_id = "M001"\n', encoding="utf-8")

    errors = validate_expectations(expectations, mappings)

    assert "requires Implementation type Profile keybinding or Profile Lua" in errors[0]
    assert "requires Availability 'Profile bound'" in errors[1]
