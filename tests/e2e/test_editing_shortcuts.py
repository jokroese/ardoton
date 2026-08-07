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
    KEY_L,
    poll_until,
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


SAMPLE_RATE = 48000
REGION_START = 0
REGION_END = 4 * SAMPLE_RATE


def _region_state(mcp) -> list[dict]:
    """track_get_regions for every track.

    tracks_list also reports the Master bus, and the region tools answer "Route is not a
    track" for one, so McpClient.tracks() filters the buses out.
    """
    return [mcp.call("track_get_regions", {"id": str(track["id"])}) for track in mcp.tracks()]


def test_probe_clear_region_fades(ardour_session) -> None:
    """S16-09. Select every region, clear fades, and dump region state around it.

    region_get_info declares additionalProperties, so whether fade state is reported --
    and under which keys -- has to be observed. Both the BackSpace and forward-delete
    chords are sent, since only one of them is reachable without Fn on a Mac keyboard.

    The script only touches audio regions (to_audioregion), and the MCP surface has no
    audio import, so this probe can only get as far as showing which keys the region
    payloads carry -- the assertion needs a fixture session that ships an audio region.
    """
    mcp = ardour_session.mcp()
    track_id, created = mcp.add_midi_region(REGION_START, REGION_END, name="Fades")
    time.sleep(SETTLE)
    _dump("probe-fades-0-tracks", {"tracks": mcp.tracks(include_buses=True), "created": created})

    ardour_session.focus_main_window()
    ardour_session.send_hotkey(KEY_A, FLAG_COMMAND)  # Editor/select-all-objects
    time.sleep(SETTLE)
    _dump("probe-fades-1-before", _region_state(mcp))
    _dump(
        "probe-fades-1-region-info",
        mcp.call("region_get_info", {"regionId": str(created["regionId"])}),
    )

    ardour_session.send_hotkey(KEY_BACKSPACE, FLAG_COMMAND | FLAG_OPTION)
    time.sleep(SETTLE)
    _dump("probe-fades-2-after-backspace", _region_state(mcp))

    ardour_session.send_hotkey(KEY_FORWARD_DELETE, FLAG_COMMAND | FLAG_OPTION)
    time.sleep(SETTLE)
    _dump("probe-fades-3-after-forward-delete", _region_state(mcp))

    assert track_id, "probe needs a track"
    pytest.skip(
        "S16-09 stays uncovered at runtime: clear-region-fades acts on audio regions only, "
        "and the MCP surface cannot create one (no import tool). Covering it needs an audio "
        "region in tests/fixtures/session/baseline."
    )


# --- S16-18 Duplicate Time -----------------------------------------------------------
#
# Live 12.4.3 duplicates the selected time across every Arrangement track and ripples later
# material, whatever the track scope of the selection (see the Live matrix in
# docs/lua-release-qualification-plan.md). Ardour's Session::cut_copy_section is
# session-wide in the same way -- it walks every playlist, splits and ripples at the
# insertion point, then pastes -- so the script keeps that operation and this asserts it.

SPAN_START = 0
SPAN_END = 4 * SAMPLE_RATE
SPAN_LENGTH = SPAN_END - SPAN_START
# Well clear of the span, so nothing but a rippling insert can move it.
LATER_START = 6 * SAMPLE_RATE
LATER_END = 8 * SAMPLE_RATE


def _spans_by_track(state: list[dict]) -> dict[str | None, list[tuple[int, int]]]:
    """Region extents per track name, which is what the duplicate assertions are about.

    Region IDs are deliberately dropped here: a redone paste is free to mint a new region
    rather than resurrect the old one, and that is not part of the behavior under test. The
    undo assertion compares the full normalized state instead, IDs included, because undo
    restores the original regions rather than recreating them.
    """
    return {
        track["trackName"]: [(region["start"], region["end"]) for region in track["regions"]]
        for track in state
    }


def test_duplicate_time_copies_the_span_across_every_track(
    ardour_session, coverage_tracker
) -> None:
    """S16-18. Cmd+Shift+D duplicates the selected time in place, session-wide, undoably."""
    mcp = ardour_session.mcp()

    first = mcp.add_midi_track("DupA")
    second = mcp.add_midi_track("DupB")
    mcp.add_midi_region_to(first, SPAN_START, SPAN_END, "A-InSpan")
    mcp.add_midi_region_to(second, SPAN_START, SPAN_END, "B-InSpan")
    mcp.add_midi_region_to(second, LATER_START, LATER_END, "B-Later")

    expected_before = {
        "DupA": [(SPAN_START, SPAN_END)],
        "DupB": [(SPAN_START, SPAN_END), (LATER_START, LATER_END)],
    }
    expected_after = {
        # The copy lands immediately after the original, on every track the session has.
        "DupA": [(SPAN_START, SPAN_END), (SPAN_END, SPAN_END + SPAN_LENGTH)],
        "DupB": [
            (SPAN_START, SPAN_END),
            (SPAN_END, SPAN_END + SPAN_LENGTH),
            # Later material is pushed back by exactly the duplicated length.
            (LATER_START + SPAN_LENGTH, LATER_END + SPAN_LENGTH),
        ],
    }

    before = poll_until(mcp.region_state, lambda state: _spans_by_track(state) == expected_before)
    assert _spans_by_track(before) == expected_before, before

    # The script needs selection extents, and a mouse drag is not available under the Dummy
    # backend. Setting the loop range and then selecting through it with a real key event
    # gives an extents pair that covers only the span -- Cmd+A would have swept in the later
    # material too and silently changed what is being duplicated.
    mcp.set_loop_range(SPAN_START, SPAN_END)
    ardour_session.focus_main_window()
    ardour_session.send_hotkey(KEY_L, FLAG_COMMAND | FLAG_SHIFT)  # select-all-in-loop-range
    time.sleep(SETTLE)

    try:
        ardour_session.send_hotkey(KEY_D, FLAG_COMMAND | FLAG_SHIFT)
        after = poll_until(mcp.region_state, lambda state: _spans_by_track(state) == expected_after)
        assert _spans_by_track(after) == expected_after, after

        copied = sum(len(regions) for regions in _spans_by_track(after).values()) - sum(
            len(regions) for regions in expected_before.values()
        )
        assert copied == 2, "one copy per track, and nothing else"

        mcp.call("session_undo")
        restored = poll_until(mcp.region_state, lambda state: state == before)
        assert restored == before, "undo must restore the exact pre-duplicate state"

        mcp.call("session_redo")
        redone = poll_until(
            mcp.region_state, lambda state: _spans_by_track(state) == expected_after
        )
        assert _spans_by_track(redone) == expected_after, redone

        coverage_tracker["S16-18"]["e2e"] = "passed"
    except Exception:
        coverage_tracker["S16-18"]["e2e"] = "failed"
        _dump("S16-18-duplicate-before", before)
        _dump("S16-18-duplicate-after", mcp.region_state())
        raise
