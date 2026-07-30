from __future__ import annotations

import xml.etree.ElementTree as ET

from support import ACTION_STATE_PATH, PROFILE, load_baseline, load_manifest

SCRIPTS = [
    "ardourton_add_audio_track.lua",
    "ardourton_add_midi_track.lua",
    "ardourton_add_return.lua",
    "ardourton_set_loop.lua",
    "ardourton_duplicate_tracks.lua",
    "ardourton_beat_production.lua",
]


def test_manifest_supported_platform_and_ardour() -> None:
    manifest = load_manifest()
    assert manifest["ardour"]["supported"] == ["9.7"]
    assert set(manifest["platforms"]) == {"macos"}


def test_expected_scripts_exist() -> None:
    for name in SCRIPTS:
        assert (PROFILE / "scripts" / name).is_file(), name


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
