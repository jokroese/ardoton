#!/usr/bin/env python3

import csv
import json
from pathlib import Path
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]


def check_manifest() -> None:
    manifest = json.loads((ROOT / "profile/manifest.json").read_text())
    assert manifest["version"] == "0.2.2"
    assert manifest["ardour"]["supported"] == ["9.7"]
    assert set(manifest["platforms"]) == {"macos"}
    assert set(manifest["lua_action_slots"]) == {"28", "29", "30", "31", "32"}


def check_keymaps() -> None:
    expected = {
        ("Global", "Primary-Level4-t"): "LuaAction/script-30",
        ("Editor", "Primary-Level4-u"): "Editor/show-plist-selector",
        ("Global", "Tab"): "Common/next-tab",
        ("Global", "Primary-t"): "LuaAction/script-28",
        ("Global", "Primary-Tertiary-t"): "LuaAction/script-29",
        ("Global", "Primary-l"): "LuaAction/script-31",
        ("Global", "F9"): "Transport/record-roll",
        ("Editor", "Primary-e"): "Editor/split-region",
        ("Editor", "Primary-j"): "Editor/editor-consolidate",
        ("Editor", "s"): "Editor/track-solo-toggle",
        ("Editor", "c"): "Editor/track-record-enable-toggle",
        ("Notes", "Primary-u"): "Notes/quantize-selected-notes",
    }

    keymap = ROOT / "profile/keybindings/macos/ardour.keys"
    root = ET.parse(keymap).getroot()
    actual = {}
    for group in root.findall("Bindings"):
        context = group.get("name")
        seen = set()
        for binding in group.findall("./Press/Binding"):
            key = binding.get("key")
            assert key not in seen, f"duplicate {context} key: {key}"
            seen.add(key)
            actual[(context, key)] = binding.get("action")

    for binding, action in expected.items():
        assert actual.get(binding) == action, (binding, actual.get(binding))

    for key in ("F9", "Primary-l"):
        matches = [
            binding
            for binding in actual
            if binding[1] == key
        ]
        assert matches == [("Global", key)], (key, matches)


def check_theme_and_preferences() -> None:
    theme = ET.parse(ROOT / "profile/theme/ardourton-ardour.colors").getroot()
    assert theme.get("theme-name") == "Ardourton"

    options = {}
    with (ROOT / "profile/preferences/ui-options.tsv").open() as source:
        for line in source:
            name, value = line.rstrip("\n").split("\t", 1)
            assert name not in options
            options[name] = value
    assert options["color-file"] == "ardourton"
    assert options["show-toolbar-cuectrl"] == "1"
    assert len(options["stripable-color-palette"].split(":")) == 12


def check_contract() -> None:
    expected_rows = {
        "workflows.csv": 50,
        "shortcuts.csv": 30,
        "terminology.csv": 25,
        "acceptance-tests.csv": 15,
        "sources.csv": 24,
    }
    for filename, count in expected_rows.items():
        with (ROOT / "contract" / filename).open(newline="", encoding="utf-8") as source:
            rows = list(csv.reader(source))
        assert len(rows) - 1 == count, filename
        assert all(len(row) == len(rows[0]) for row in rows), filename


def check_action_state() -> None:
    state = (
        ROOT / "profile/ui-scripts/ardourton-actions.lua-state"
    ).read_text(encoding="utf-8")
    for slot, name in {
        28: "Add Stereo Audio Track",
        29: "Add MIDI Track",
        30: "Add Return",
        31: "Set and Toggle Loop",
        32: "Duplicate Tracks",
    }.items():
        assert f"scripts[{slot}]" in state
        assert f"Ardourton: {name}" in state


if __name__ == "__main__":
    check_manifest()
    check_keymaps()
    check_theme_and_preferences()
    check_contract()
    check_action_state()
    print("profile checks passed")
