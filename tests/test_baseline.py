from __future__ import annotations

import re
import tomllib

from support import (
    ACTION_STATE_PATH,
    KEYMAP_PATH,
    ROOT,
    load_baseline,
    load_manifest,
    profile_file_inventory,
    sha256_file,
)


def test_baseline_manifest_version() -> None:
    baseline = load_baseline()
    manifest = load_manifest()
    assert manifest["version"] == baseline["manifest_version"]


def test_release_versions_are_consistent() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    manifest = load_manifest()
    baseline = load_baseline()
    installer = (ROOT / "installer" / "macos.sh").read_text(encoding="utf-8")
    receipt_version = re.search(r'print -r -- "version=([^\"]+)"', installer)

    assert receipt_version is not None
    assert {
        project["project"]["version"],
        manifest["version"],
        baseline["manifest_version"],
        receipt_version.group(1),
    } == {manifest["version"]}


def test_baseline_keymap_hash() -> None:
    baseline = load_baseline()
    assert sha256_file(KEYMAP_PATH) == baseline["macos_keymap_sha256"]


def test_baseline_action_state_hash() -> None:
    baseline = load_baseline()
    assert sha256_file(ACTION_STATE_PATH) == baseline["lua_action_state_sha256"]


def test_baseline_lua_slots() -> None:
    baseline = load_baseline()
    manifest = load_manifest()
    assert manifest["lua_action_slots"] == baseline["lua_action_slots"]


def test_baseline_profile_inventory() -> None:
    baseline = load_baseline()
    assert profile_file_inventory() == baseline["profile_files"]
