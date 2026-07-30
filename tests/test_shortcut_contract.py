from __future__ import annotations

import json
import shutil
import subprocess
import sys

from tools.validate_shortcuts import (
    report,
    section_report,
    validate_contract,
    validate_expectations,
)

from support import CONTRACT


def copied_contract(tmp_path):
    destination = tmp_path / "contract"
    shutil.copytree(CONTRACT, destination)
    return destination


def write(path, document) -> None:
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


def test_real_shortcut_contract_is_valid() -> None:
    assert validate_contract() == []
    assert (
        validate_expectations(
            CONTRACT.parent / "tests" / "expectations.toml", CONTRACT / "shortcut-mappings"
        )
        == []
    )


def test_rejects_json_schema_failure(tmp_path) -> None:
    contract = copied_contract(tmp_path)
    source = contract / "ableton-shortcuts.json"
    document = json.loads(source.read_text(encoding="utf-8"))
    document["unexpected"] = True
    write(source, document)
    assert (
        "is not valid under any of the given schemas"
        in validate_contract(source, contract / "shortcut-mappings")[0]
    )


def test_rejects_duplicate_json_keys(tmp_path) -> None:
    contract = copied_contract(tmp_path)
    source = contract / "ableton-shortcuts.json"
    source.write_text(
        '{"documentType":"shortcut-sources","documentType":"shortcut-sources"}', encoding="utf-8"
    )
    assert (
        "duplicate JSON key 'documentType'"
        in validate_contract(source, contract / "shortcut-mappings")[0]
    )


def test_rejects_missing_coverage(tmp_path) -> None:
    contract = copied_contract(tmp_path)
    mapping = contract / "shortcut-mappings" / "01.json"
    document = json.loads(mapping.read_text(encoding="utf-8"))
    document["shortcuts"].pop()
    write(mapping, document)
    assert "has no mapping" in "\n".join(
        validate_contract(contract / "ableton-shortcuts.json", contract / "shortcut-mappings")
    )


def test_rejects_multiple_preferred_mappings(tmp_path) -> None:
    contract = copied_contract(tmp_path)
    mapping = contract / "shortcut-mappings" / "01.json"
    document = json.loads(mapping.read_text(encoding="utf-8"))
    record = document["shortcuts"][1]
    record["mappings"][1]["role"] = "Preferred"
    write(mapping, document)
    assert "requires one Preferred mapping" in "\n".join(
        validate_contract(contract / "ableton-shortcuts.json", contract / "shortcut-mappings")
    )


def test_audit_statuses_have_required_mapping_roles(tmp_path) -> None:
    contract = copied_contract(tmp_path)
    mapping = contract / "shortcut-mappings" / "01.json"
    document = json.loads(mapping.read_text(encoding="utf-8"))
    statuses = {record["auditStatus"] for record in document["shortcuts"]}
    assert "Needs audit" not in statuses
    assert "Partially assessed" in statuses
    assert "Assessed" in statuses
    write(mapping, document)
    assert (
        validate_contract(contract / "ableton-shortcuts.json", contract / "shortcut-mappings") == []
    )


def test_rejects_assessed_without_preferred_mapping(tmp_path) -> None:
    contract = copied_contract(tmp_path)
    mapping = contract / "shortcut-mappings" / "01.json"
    document = json.loads(mapping.read_text(encoding="utf-8"))
    document["shortcuts"][2]["auditStatus"] = "Assessed"
    write(mapping, document)
    assert "assessed source requires one Preferred mapping" in "\n".join(
        validate_contract(contract / "ableton-shortcuts.json", contract / "shortcut-mappings")
    )


def test_rejects_partially_assessed_with_preferred_mapping(tmp_path) -> None:
    contract = copied_contract(tmp_path)
    mapping = contract / "shortcut-mappings" / "01.json"
    document = json.loads(mapping.read_text(encoding="utf-8"))
    document["shortcuts"][2]["mappings"][0]["role"] = "Preferred"
    write(mapping, document)
    assert "partially assessed source requires mappings without a Preferred mapping" in "\n".join(
        validate_contract(contract / "ableton-shortcuts.json", contract / "shortcut-mappings")
    )


def test_mapping_tuples_are_unique_per_source(tmp_path) -> None:
    contract = copied_contract(tmp_path)
    mapping = contract / "shortcut-mappings" / "01.json"
    document = json.loads(mapping.read_text(encoding="utf-8"))
    first, second = document["shortcuts"][2:4]
    second["mappings"][0].update(first["mappings"][0])
    write(mapping, document)
    assert (
        validate_contract(contract / "ableton-shortcuts.json", contract / "shortcut-mappings") == []
    )
    second["mappings"].append(first["mappings"][0].copy())
    write(mapping, document)
    assert "duplicate mapping tuple" in "\n".join(
        validate_contract(contract / "ableton-shortcuts.json", contract / "shortcut-mappings")
    )


def test_rejects_exact_without_behavior_evidence(tmp_path) -> None:
    contract = copied_contract(tmp_path)
    mapping = contract / "shortcut-mappings" / "01.json"
    document = json.loads(mapping.read_text(encoding="utf-8"))
    item = document["shortcuts"][1]["mappings"][1]
    item["mappingClass"] = "Exact"
    item["evidence"] = [item["evidence"][0]]
    write(mapping, document)
    assert "Exact requires behavior evidence" in "\n".join(
        validate_contract(contract / "ableton-shortcuts.json", contract / "shortcut-mappings")
    )


def test_rejects_profile_token_collision(tmp_path) -> None:
    contract = copied_contract(tmp_path)
    mapping = contract / "shortcut-mappings" / "01.json"
    document = json.loads(mapping.read_text(encoding="utf-8"))
    item = document["shortcuts"][2]["mappings"][0]
    item["role"] = "Preferred"
    item["status"] = "Proposed"
    write(mapping, document)
    keymap = tmp_path / "ardour.keys"
    keymap.write_text(
        '<BindingSet><Bindings name="Global"><Press>'
        '<Binding key="Tab" action="Other" />'
        "</Press></Bindings></BindingSet>",
        encoding="utf-8",
    )
    assert "key token collision" in "\n".join(
        validate_contract(
            contract / "ableton-shortcuts.json", contract / "shortcut-mappings", keymap
        )
    )


def test_formatter_check_and_section_report() -> None:
    result = subprocess.run(
        [sys.executable, "tools/format_shortcuts.py", "--check"],
        cwd=CONTRACT.parent,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    summary = report(CONTRACT / "ableton-shortcuts.json", CONTRACT / "shortcut-mappings", "01")
    assert "Source input kinds:" in summary
    assert "Mapping statuses:" in summary
    output = section_report(
        CONTRACT / "ableton-shortcuts.json", CONTRACT / "shortcut-mappings", "01"
    )
    assert (
        "S01-03 | Toggle Session/Arrangement View | Keyboard | Main window | Partially assessed"
        in output
    )
    assert (
        "  Mapping | Current fallback | Profile keybinding | Similar | Implemented | "
        "Common/next-tab" in output
    )
    assert "    Evidence | Profile binding | Binding exists | Confirmed |" in output
    result = subprocess.run(
        [sys.executable, "tools/validate_shortcuts.py", "--report", "--section", "01"],
        cwd=CONTRACT.parent,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Source input kinds:" in result.stdout
    assert "Section 01 joined report:" in result.stdout
