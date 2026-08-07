"""Discovery probes for the three Phase 2 shortcuts that are not loop-range edits.

Unlike the loop family, these need editor state the MCP surface does not expose directly:
the grid type lives in the session's instant.xml, and fades and time duplication need a
selection. Each test here dumps what it can see so the assertions can be written from an
observed payload rather than a guess -- the same approach that settled the marker JSON
shape in test_loop_shortcuts.
"""

from __future__ import annotations

import json
import time

import pytest

from e2e.driver import (
    FLAG_COMMAND,
    FLAG_OPTION,
    FLAG_SHIFT,
    KEY_3,
    KEY_A,
    KEY_BACKSPACE,
    KEY_D,
    KEY_FORWARD_DELETE,
    KEY_R,
)

pytestmark = [pytest.mark.e2e, pytest.mark.requires_ardour]

SETTLE = 1.0

# Ardour's triplet grid series stops at GridTypeBeatDiv24 (1/16 triplets); there is no
# 1/32 triplet type. The profile ships GridTypeBeatDiv32 as its default, so the toggle is
# a deliberate no-op until the grid is 1/2, 1/4, 1/8 or 1/16.
TOGGLEABLE_GRIDS = {
    "GridTypeBeatDiv2": "GridTypeBeatDiv3",
    "GridTypeBeatDiv4": "GridTypeBeatDiv6",
    "GridTypeBeatDiv8": "GridTypeBeatDiv12",
    "GridTypeBeatDiv16": "GridTypeBeatDiv24",
}


def _dump(label: str, payload: object) -> None:
    from support import ensure_results_dir

    destination = ensure_results_dir() / "e2e" / f"{label}.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2, sort_keys=True, default=str)
    destination.write_text(text, encoding="utf-8")
    print(f"\n----- {label} -----\n{text}\n")


def _instant_xml(ardour_session) -> dict[str, object]:
    """Everything we might need to locate the editor's persisted grid type."""
    candidates = {
        "session_dir/instant.xml": ardour_session.session_dir / "instant.xml",
        "config_dir/instant.xml": ardour_session.config_dir / "instant.xml",
    }
    out: dict[str, object] = {}
    for label, path in candidates.items():
        out[label] = path.read_text(encoding="utf-8") if path.is_file() else None
    return out


def test_probe_triplet_grid(ardour_session) -> None:
    """S13-04. Find where the grid type is observable and whether Cmd+3 moves it.

    Dumps instant.xml before, after Cmd+3, and after a session save, so we can tell both
    what the grid was and whether the file updates without an explicit save.
    """
    mcp = ardour_session.mcp()
    _dump("probe-grid-0-before", _instant_xml(ardour_session))

    ardour_session.focus_main_window()
    ardour_session.send_hotkey(KEY_3, FLAG_COMMAND)
    time.sleep(SETTLE)
    _dump("probe-grid-1-after-cmd3", _instant_xml(ardour_session))

    mcp.call("session_save")
    time.sleep(SETTLE)
    _dump("probe-grid-2-after-save", _instant_xml(ardour_session))


def test_probe_clear_region_fades(ardour_session) -> None:
    """S16-09. Select every region, clear fades, and dump region state around it.

    region_get_info declares additionalProperties, so whether fade state is reported --
    and under which keys -- has to be observed. Both the BackSpace and forward-delete
    chords are sent, since only one of them is reachable without Fn on a Mac keyboard.
    """
    mcp = ardour_session.mcp()
    tracks = mcp.call("tracks_list")
    _dump("probe-fades-0-tracks", tracks)

    def region_state() -> list[dict]:
        states = []
        for track in tracks.get("tracks", []):
            track_id = track.get("id")
            if track_id is None:
                continue
            states.append(mcp.call("track_get_regions", {"id": str(track_id)}))
        return states

    ardour_session.focus_main_window()
    ardour_session.send_hotkey(KEY_A, FLAG_COMMAND)  # Editor/select-all-objects
    time.sleep(SETTLE)
    _dump("probe-fades-1-before", region_state())

    ardour_session.send_hotkey(KEY_BACKSPACE, FLAG_COMMAND | FLAG_OPTION)
    time.sleep(SETTLE)
    _dump("probe-fades-2-after-backspace", region_state())

    ardour_session.send_hotkey(KEY_FORWARD_DELETE, FLAG_COMMAND | FLAG_OPTION)
    time.sleep(SETTLE)
    _dump("probe-fades-3-after-forward-delete", region_state())


def test_probe_duplicate_time(ardour_session) -> None:
    """S16-18. Establish a real time selection, then duplicate it.

    A time selection is what the S16-11 case could not create. Switching to Range mouse
    mode first should make Cmd+A select a time range rather than objects; this dumps the
    region list before and after so we can see whether anything was duplicated and by how
    much.
    """
    mcp = ardour_session.mcp()
    tracks = mcp.call("tracks_list")

    def region_state() -> list[dict]:
        states = []
        for track in tracks.get("tracks", []):
            track_id = track.get("id")
            if track_id is None:
                continue
            states.append(mcp.call("track_get_regions", {"id": str(track_id)}))
        return states

    ardour_session.focus_main_window()
    ardour_session.send_hotkey(KEY_R)  # Editor/set-mouse-mode-range
    time.sleep(SETTLE)
    ardour_session.send_hotkey(KEY_A, FLAG_COMMAND)
    time.sleep(SETTLE)
    _dump("probe-duplicate-0-before", region_state())

    ardour_session.send_hotkey(KEY_D, FLAG_COMMAND | FLAG_SHIFT)
    time.sleep(SETTLE * 2)
    _dump("probe-duplicate-1-after", region_state())
