from __future__ import annotations

import csv
import json

from support import CONTRACT, contract_row_count, load_expectations, shortcut_sources

EXPECTED_ROWS = {
    "workflows.csv": 51,
    "terminology.csv": 25,
    "acceptance-tests.csv": 16,
    "sources.csv": 24,
}


def test_contract_csv_row_counts() -> None:
    for filename, count in EXPECTED_ROWS.items():
        assert contract_row_count(filename) == count, filename


def test_contract_csv_rectangular() -> None:
    for filename in EXPECTED_ROWS:
        with (CONTRACT / filename).open(newline="", encoding="utf-8") as source:
            rows = list(csv.reader(source))
        assert rows
        width = len(rows[0])
        assert all(len(row) == width for row in rows), filename


def test_source_shortcut_count_is_frozen() -> None:
    assert len(shortcut_sources()) == 339


def test_mapping_documents_cover_sources_once() -> None:
    records = []
    for path in (CONTRACT / "shortcut-mappings").glob("*.json"):
        records.extend(json.loads(path.read_text(encoding="utf-8"))["shortcuts"])
    assert {record["sourceId"] for record in records} == set(shortcut_sources())
    assert len(records) == len(shortcut_sources())


def test_expectation_source_ids_exist() -> None:
    source_ids = shortcut_sources()
    bindings, exclusives = load_expectations()
    for binding in bindings:
        assert binding.source_id in source_ids, binding.source_id
    for exclusive in exclusives:
        assert exclusive.source_id in source_ids, exclusive.source_id


def test_expectation_context_key_unique() -> None:
    """Two rows may claim the same key only if they expect the same action.

    S08-11 and S16-12 legitimately share the loop-resize bindings (one Lua slot serves both
    Live behaviors); what this must still catch is two expectations demanding different
    actions on one key, which the keymap could never satisfy.
    """
    bindings, _ = load_expectations()
    seen: dict[tuple[str, str], str] = {}
    for binding in bindings:
        pair = (binding.context, binding.key)
        if pair in seen:
            assert seen[pair] == binding.action, f"conflicting expectations for {pair}"
        seen[pair] = binding.action
