from __future__ import annotations

import csv

from support import CONTRACT, contract_ids, contract_row_count, load_expectations

EXPECTED_ROWS = {
    "workflows.csv": 50,
    "ableton-shortcuts.csv": 339,
    "shortcuts-map.csv": 340,
    "shortcut-evidence.csv": 44,
    "terminology.csv": 25,
    "acceptance-tests.csv": 15,
    "sources.csv": 24,
}


def test_contract_row_counts() -> None:
    for filename, count in EXPECTED_ROWS.items():
        assert contract_row_count(filename) == count, filename


def test_contract_csv_rectangular() -> None:
    for filename in EXPECTED_ROWS:
        with (CONTRACT / filename).open(newline="", encoding="utf-8") as source:
            rows = list(csv.reader(source))
        assert rows
        width = len(rows[0])
        assert all(len(row) == width for row in rows), filename


def test_expectation_mapping_ids_exist_in_shortcuts_map() -> None:
    mapping_ids = contract_ids("shortcuts-map.csv", "Mapping ID")
    bindings, exclusives = load_expectations()
    for binding in bindings:
        assert binding.mapping_id in mapping_ids, binding.mapping_id
    for exclusive in exclusives:
        assert exclusive.mapping_id in mapping_ids, exclusive.mapping_id


def test_expectation_context_key_unique() -> None:
    bindings, _ = load_expectations()
    seen: set[tuple[str, str]] = set()
    for binding in bindings:
        pair = (binding.context, binding.key)
        assert pair not in seen, f"duplicate expectation {pair}"
        seen.add(pair)
