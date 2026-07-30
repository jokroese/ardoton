from __future__ import annotations

import csv

from tools.validate_shortcuts import (
    EVIDENCE_FIELDS,
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
        {
            "Mapping ID": mapping_id,
            "Ableton shortcut ID": source_id,
            "Mapping role": "Placeholder",
            "Status": "Needs audit",
        }
    )
    row.update(values)
    return row


def test_real_shortcut_contract_is_valid() -> None:
    assert (
        validate_contract(
            CONTRACT / "ableton-shortcuts.csv",
            CONTRACT / "shortcuts-map.csv",
            CONTRACT / "shortcut-evidence.csv",
        )
        == []
    )


def test_rejects_invalid_controlled_value(tmp_path) -> None:
    sources = tmp_path / "sources.csv"
    mappings = tmp_path / "mappings.csv"
    write_csv(sources, SOURCE_FIELDS, [source("S01-01")])
    write_csv(mappings, MAPPING_FIELDS, [mapping("M001", "S01-01", Availability="Elsewhere")])

    errors = validate_contract(sources, mappings)

    assert "invalid Availability 'Elsewhere'" in errors[0]


def test_rejects_invalid_evidence_reference(tmp_path) -> None:
    sources = tmp_path / "sources.csv"
    mappings = tmp_path / "mappings.csv"
    write_csv(sources, SOURCE_FIELDS, [source("S01-01")])
    evidence = tmp_path / "evidence.csv"
    write_csv(mappings, MAPPING_FIELDS, [mapping("M001", "S01-01")])
    write_csv(
        evidence,
        EVIDENCE_FIELDS,
        [
            {
                "Evidence ID": "E001",
                "Mapping ID": "M999",
                "Evidence kind": "Action registration",
                "Claim": "Target exists",
                "Reference": "test",
                "Result": "Candidate",
            }
        ],
    )

    assert "unknown Mapping ID 'M999'" in validate_contract(sources, mappings, evidence)[0]


def test_rejects_source_without_mapping(tmp_path) -> None:
    sources = tmp_path / "sources.csv"
    mappings = tmp_path / "mappings.csv"
    write_csv(sources, SOURCE_FIELDS, [source("S01-01"), source("S01-02")])
    write_csv(mappings, MAPPING_FIELDS, [mapping("M001", "S01-01")])

    errors = validate_contract(sources, mappings)

    assert "source ID 'S01-02': has no mapping" in errors


def test_rejects_exact_without_behavior_evidence(tmp_path) -> None:
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
                Status="Proposed",
                **{"Mapping role": "Preferred"},
                **{
                    "Proposed macOS": "Cmd+A",
                    "Ardour context": "Global",
                    "Ardour key token": "Primary-a",
                    "Ardour action target": "Action/test",
                    "Implementation type": "Profile keybinding",
                    "Mapping class": "Exact",
                    "Availability": "Native bound",
                },
            )
        ],
    )

    evidence = tmp_path / "evidence.csv"
    write_csv(
        evidence,
        EVIDENCE_FIELDS,
        [
            {
                "Evidence ID": "E001",
                "Mapping ID": "M001",
                "Evidence kind": "Action registration",
                "Claim": "Target exists",
                "Reference": "test",
                "Result": "Candidate",
            }
        ],
    )
    assert "Exact requires behavior evidence" in validate_contract(sources, mappings, evidence)[0]


def test_expectation_requires_profile_bound_keybinding_or_lua_mapping(tmp_path) -> None:
    mappings = tmp_path / "mappings.csv"
    expectations = tmp_path / "expectations.toml"
    write_csv(mappings, MAPPING_FIELDS, [mapping("M001", "S01-01")])
    expectations.write_text('[[binding]]\nmapping_id = "M001"\n', encoding="utf-8")

    errors = validate_expectations(expectations, mappings)

    assert "requires Implementation type Profile keybinding or Profile Lua" in errors[0]
    assert "requires Availability 'Profile bound'" in errors[1]


def test_rejects_missing_capability_audit(tmp_path) -> None:
    sources = tmp_path / "sources.csv"
    mappings = tmp_path / "mappings.csv"
    evidence = tmp_path / "evidence.csv"
    write_csv(sources, SOURCE_FIELDS, [source("S01-01")])
    write_csv(
        mappings,
        MAPPING_FIELDS,
        [
            mapping(
                "M001",
                "S01-01",
                Status="Proposed",
                **{
                    "Mapping role": "Preferred",
                    "Ardour context": "Global",
                    "Ardour action target": "Action/test",
                    "Implementation type": "Ardour UI patch",
                    "Mapping class": "Similar",
                    "Availability": "Missing",
                },
            )
        ],
    )
    write_csv(
        evidence,
        EVIDENCE_FIELDS,
        [
            {
                "Evidence ID": "E001",
                "Mapping ID": "M001",
                "Evidence kind": "Callback implementation",
                "Claim": "UI only",
                "Reference": "test",
                "Result": "Candidate",
            }
        ],
    )

    assert (
        "Missing requires capability audit evidence"
        in validate_contract(sources, mappings, evidence)[0]
    )


def test_rejects_profile_token_collision(tmp_path) -> None:
    sources = tmp_path / "sources.csv"
    mappings = tmp_path / "mappings.csv"
    evidence = tmp_path / "evidence.csv"
    keymap = tmp_path / "ardour.keys"
    write_csv(sources, SOURCE_FIELDS, [source("S01-01")])
    write_csv(
        mappings,
        MAPPING_FIELDS,
        [
            mapping(
                "M001",
                "S01-01",
                Status="Proposed",
                **{
                    "Mapping role": "Preferred",
                    "Ardour context": "Global",
                    "Ardour key token": "Primary-a",
                    "Ardour action target": "Action/test",
                    "Implementation type": "Profile keybinding",
                    "Mapping class": "Similar",
                    "Availability": "Profile bound",
                },
            )
        ],
    )
    write_csv(
        evidence,
        EVIDENCE_FIELDS,
        [
            {
                "Evidence ID": "E001",
                "Mapping ID": "M001",
                "Evidence kind": "Profile binding",
                "Claim": "Binding exists",
                "Reference": "test",
                "Result": "Confirmed",
            }
        ],
    )
    keymap.write_text(
        "<BindingSet><Bindings name=\"Global\"><Press>"
        "<Binding key=\"Primary-a\" action=\"Action/other\" />"
        "</Press></Bindings></BindingSet>",
        encoding="utf-8",
    )

    assert "key token collision" in validate_contract(sources, mappings, evidence, keymap)[0]
