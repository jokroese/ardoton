from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET

from support import ACTION_STATE_PATH, PROFILE, ROOT, load_baseline, load_manifest


def _script_manifest_inventory() -> tuple[set[str], set[str]]:
    """(slotted sources, unslotted sources) declared by profile/scripts/manifest.json."""
    manifest = json.loads((PROFILE / "scripts" / "manifest.json").read_text(encoding="utf-8"))
    slotted = {entry["source"] for entry in manifest["slots"]}
    unslotted = set(manifest["unslotted"])
    return slotted, unslotted


def _installer_script_names() -> set[str]:
    installer = (ROOT / "installer" / "macos.sh").read_text(encoding="utf-8")
    block = re.search(r"^script_names=\(\n(.*?)\n\)$", installer, re.MULTILINE | re.DOTALL)
    assert block is not None
    return set(block.group(1).split())


def test_script_manifest_is_the_exact_inventory() -> None:
    """profile/scripts/manifest.json is the source of truth for the script set.

    Every slotted and unslotted source must exist, their union must equal the .lua files
    that are actually in the profile, and the installer's hand-maintained list must install
    exactly that set -- no stale entries, no forgotten scripts.
    """
    slotted, unslotted = _script_manifest_inventory()
    assert slotted, "manifest declares no slots"
    assert not (slotted & unslotted), "a source cannot be both slotted and unslotted"

    declared = slotted | unslotted
    for name in sorted(declared):
        assert (PROFILE / "scripts" / name).is_file(), f"declared but missing: {name}"

    on_disk = {path.name for path in (PROFILE / "scripts").glob("*.lua")}
    assert declared == on_disk

    assert _installer_script_names() == declared


def test_manifest_supported_platform_and_ardour() -> None:
    manifest = load_manifest()
    assert manifest["ardour"]["supported"] == ["9.7"]
    assert set(manifest["platforms"]) == {"macos"}


def test_theme_and_preferences() -> None:
    theme = ET.parse(PROFILE / "theme" / "ardourton-ardour.colors").getroot()
    assert theme.get("theme-name") == "Ardourton"

    options: dict[str, str] = {}
    with (PROFILE / "preferences" / "ui-options.tsv").open(encoding="utf-8") as source:
        for line in source:
            name, value = line.rstrip("\n").split("\t", 1)
            assert name not in options
            options[name] = value
    assert options["color-file"] == "ardourton"
    assert options["show-toolbar-cuectrl"] == "1"
    assert len(options["stripable-color-palette"].split(":")) == 12
    assert options["snap-threshold"] == "10"
    assert options["ruler-granularity"] == "250"
    assert options["snap-target"] == "SnapTargetBoth"
    assert options["rulers-follow-grid"] == "1"


def test_grid_snap_defaults_match_manifest() -> None:
    manifest = load_manifest()
    defaults = manifest["grid_snap_defaults"]
    options: dict[str, str] = {}
    with (PROFILE / "preferences" / "ui-options.tsv").open(encoding="utf-8") as source:
        for line in source:
            name, value = line.rstrip("\n").split("\t", 1)
            options[name] = value
    for name, value in defaults["ui_config"].items():
        assert options[name] == value, name
    assert defaults["instant_xml"]["Editor"] == {
        "grid-type": "GridTypeBeatDiv32",
        "snap-mode": "SnapMagnetic",
    }
    assert defaults["instant_xml"]["MIDICueEditor"] == {
        "grid-type": "GridTypeBeatDiv32",
        "snap-mode": "SnapMagnetic",
    }


def test_lua_action_slots_match_baseline() -> None:
    baseline = load_baseline()
    state = ACTION_STATE_PATH.read_text(encoding="utf-8")
    for slot, name in baseline["lua_action_slots"].items():
        assert f"scripts[{slot}]" in state
        assert name in state


def test_no_unexpected_lua_action_slots() -> None:
    baseline = load_baseline()
    state = ACTION_STATE_PATH.read_text(encoding="utf-8")
    allowed = set(baseline["lua_action_slots"])
    # Serialized form uses scripts[N] = ...
    import re

    found = set(re.findall(r"scripts\[(\d+)\]", state))
    assert found == allowed
