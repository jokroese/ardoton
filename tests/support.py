"""Shared paths and loaders for the Ardourton regression harness."""

from __future__ import annotations

import csv
import hashlib
import json
import tomllib
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / "tests"
PROFILE = ROOT / "profile"
CONTRACT = ROOT / "contract"
BASELINE_PATH = TESTS / "baseline.json"
EXPECTATIONS_PATH = TESTS / "expectations.toml"
KEYMAP_PATH = PROFILE / "keybindings" / "macos" / "ardour.keys"
ACTION_STATE_PATH = PROFILE / "ui-scripts" / "ardourton-actions.lua-state"
MANIFEST_PATH = PROFILE / "manifest.json"
RESULTS_DIR = ROOT / "test-results"

ARDOUR_APP = Path("/Applications/Ardour9.app")
ARDOUR_BIN = ARDOUR_APP / "Contents" / "MacOS" / "Ardour9"
ARDOUR_LUA = ARDOUR_APP / "Contents" / "MacOS" / "ardour9-lua"
REAL_CONFIG = Path.home() / "Library" / "Preferences" / "Ardour9"


@dataclass(frozen=True)
class BindingExpectation:
    feature: str
    context: str
    key: str
    action: str


@dataclass(frozen=True)
class ExclusiveExpectation:
    feature: str
    key: str
    contexts: tuple[str, ...]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def load_baseline() -> dict:
    return json.loads(BASELINE_PATH.read_text(encoding="utf-8"))


def load_manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def load_expectations() -> tuple[list[BindingExpectation], list[ExclusiveExpectation]]:
    data = tomllib.loads(EXPECTATIONS_PATH.read_text(encoding="utf-8"))
    bindings = [
        BindingExpectation(
            feature=row["feature"],
            context=row["context"],
            key=row["key"],
            action=row["action"],
        )
        for row in data.get("binding", [])
    ]
    exclusives = [
        ExclusiveExpectation(
            feature=row["feature"],
            key=row["key"],
            contexts=tuple(row["contexts"]),
        )
        for row in data.get("exclusive", [])
    ]
    return bindings, exclusives


def load_keymap() -> dict[tuple[str, str], str]:
    root = ET.parse(KEYMAP_PATH).getroot()
    actual: dict[tuple[str, str], str] = {}
    for group in root.findall("Bindings"):
        context = group.get("name") or ""
        for binding in group.findall("./Press/Binding"):
            key = binding.get("key") or ""
            action = binding.get("action") or ""
            actual[(context, key)] = action
    return actual


def keymap_duplicates() -> list[tuple[str, str]]:
    root = ET.parse(KEYMAP_PATH).getroot()
    dupes: list[tuple[str, str]] = []
    for group in root.findall("Bindings"):
        context = group.get("name") or ""
        seen: set[str] = set()
        for binding in group.findall("./Press/Binding"):
            key = binding.get("key") or ""
            if key in seen:
                dupes.append((context, key))
            seen.add(key)
    return dupes


def contract_ids(filename: str, id_column: str = "ID") -> set[str]:
    path = CONTRACT / filename
    with path.open(newline="", encoding="utf-8") as source:
        rows = list(csv.DictReader(source))
    return {row[id_column] for row in rows if row.get(id_column)}


def contract_row_count(filename: str) -> int:
    with (CONTRACT / filename).open(newline="", encoding="utf-8") as source:
        rows = list(csv.reader(source))
    return max(len(rows) - 1, 0)


def profile_file_inventory() -> list[str]:
    return sorted(
        str(path.relative_to(ROOT)).replace("\\", "/")
        for path in PROFILE.rglob("*")
        if path.is_file()
    )


def format_binding_failure(
    feature: str,
    expected_context: str,
    expected_key: str,
    expected_action: str,
    actual_context: str | None,
    actual_key: str | None,
    actual_action: str | None,
) -> str:
    expected = f"{expected_context} | {expected_key} | {expected_action}"
    if actual_action is None:
        actual = "missing"
    else:
        actual = f"{actual_context} | {actual_key} | {actual_action}"
    return f"{feature} missing:\nexpected {expected}\nactual   {actual}"


def ensure_results_dir() -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    return RESULTS_DIR
