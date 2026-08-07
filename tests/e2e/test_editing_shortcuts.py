"""Runtime coverage for the three Phase 2 Lua shortcuts that are not loop-range edits.

Unlike the loop family, these need editor state the MCP surface does not expose directly:
the grid type is only observable in the session's instant.xml, and fades and time
duplication both need a selection. Each test establishes that state through real Editor key
dispatch or through the session fixture, then asserts against normalized state rather than
a screenshot.
"""

from __future__ import annotations

import json
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass

import pytest

from e2e.driver import (
    FLAG_COMMAND,
    FLAG_OPTION,
    FLAG_SHIFT,
    KEY_3,
    KEY_A,
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

UNTOGGLEABLE_GRID = "GridTypeBeatDiv32"


def _dump(label: str, payload: object) -> None:
    from support import ensure_results_dir

    destination = ensure_results_dir() / "e2e" / f"{label}.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2, sort_keys=True, default=str)
    destination.write_text(text, encoding="utf-8")
    print(f"\n----- {label} -----\n{text}\n")


def _toggle_grid(ardour_session) -> None:
    ardour_session.focus_main_window()
    ardour_session.send_hotkey(KEY_3, FLAG_COMMAND)  # Editor Primary-3 -> LuaAction/script-19


@pytest.mark.parametrize(
    ("ardour_session", "binary", "triplet"),
    [({"grid_type": binary}, binary, triplet) for binary, triplet in TOGGLEABLE_GRIDS.items()],
    indirect=["ardour_session"],
    ids=list(TOGGLEABLE_GRIDS),
)
def test_triplet_grid_round_trips(ardour_session, coverage_tracker, binary, triplet) -> None:
    """S13-04. Cmd+3 swaps a binary subdivision for its triplet, and back again.

    The pairs come from the script's own two lookup tables; a reversed or missing entry
    fails here rather than surfacing as a grid that quietly stops toggling.
    """
    assert ardour_session.editor_grid_type() == binary, "fixture did not seed the starting grid"

    try:
        _toggle_grid(ardour_session)
        got = poll_until(ardour_session.editor_grid_type, lambda value: value == triplet)
        assert got == triplet, f"Cmd+3 on {binary} should select {triplet}"

        _toggle_grid(ardour_session)
        got = poll_until(ardour_session.editor_grid_type, lambda value: value == binary)
        assert got == binary, f"Cmd+3 on {triplet} should return to {binary}"

        coverage_tracker["S13-04"]["e2e"] = "passed"
    except Exception:
        coverage_tracker["S13-04"]["e2e"] = "failed"
        _dump(f"S13-04-{binary}", ardour_session.editor_grid_type())
        raise


@pytest.mark.parametrize(
    "ardour_session", [{"grid_type": UNTOGGLEABLE_GRID}], indirect=True, ids=[UNTOGGLEABLE_GRID]
)
def test_triplet_grid_leaves_the_profile_default_alone(ardour_session, coverage_tracker) -> None:
    """S13-04. The shipped 1/32 default has no triplet counterpart, so Cmd+3 does nothing.

    Ardour's triplet series stops at GridTypeBeatDiv24. The four round-trip cases above
    prove the key reaches the action in an otherwise identical session, so a grid that does
    not move here is the documented no-op rather than a dead binding.
    """
    assert ardour_session.editor_grid_type() == UNTOGGLEABLE_GRID

    try:
        _toggle_grid(ardour_session)
        # Nothing should be written at all; give a change every chance to appear first.
        settled = poll_until(
            ardour_session.editor_grid_type,
            lambda value: value != UNTOGGLEABLE_GRID,
            timeout=3.0,
        )
        assert settled == UNTOGGLEABLE_GRID, "Cmd+3 must not move a grid with no triplet pair"
        coverage_tracker["S13-04"]["e2e"] = "passed"
    except Exception:
        coverage_tracker["S13-04"]["e2e"] = "failed"
        raise


SAMPLE_RATE = 48000
REGION_START = 0
REGION_END = 4 * SAMPLE_RATE


# --- S16-09 Clear Region Fades -------------------------------------------------------
#
# The audio-fades fixture ships one audio track ("Audio 1") whose region "fades" has an
# active 12000-sample fade-in and 6000-sample fade-out. Fade state is not on the MCP
# surface, so the assertions read the saved session XML, where AudioRegion serializes
# fade-in-active/fade-out-active and each fade's AutomationList (whose last event is the
# fade length). Ardour clamps set_fade_*_length to 64 samples, so "cleared" means inactive
# with a 64-sample length -- a zero-length fade is not representable.

FIXTURE_FADE_IN = 12000
FIXTURE_FADE_OUT = 6000
MIN_FADE = 64


@dataclass(frozen=True)
class FadeState:
    in_active: bool
    out_active: bool
    in_samples: int
    out_samples: int


def _fade_state(ardour_session) -> FadeState:
    """Fade state of the fixture's audio region, from the saved session file.

    The fade length is the 'when' of the fade AutomationList's last event, serialized as
    a<superclocks>; superclocks-per-second and the sample rate come from the same file, so
    the conversion cannot drift from the fixture.
    """
    root = ET.parse(ardour_session.session_file).getroot()
    superclocks = int(root.find("TempoMap").get("superclocks-per-second"))
    rate = int(root.get("sample-rate"))
    per_sample = superclocks // rate

    region = next(
        region
        for region in root.iterfind(".//Playlists/Playlist/Region")
        if region.get("type") == "audio"
    )

    def fade_samples(kind: str) -> int:
        events = region.find(f"./{kind}/AutomationList/events")
        assert events is not None and events.text, f"no {kind} events in saved session"
        last_when = events.text.strip().splitlines()[-1].split()[0]
        assert last_when.startswith("a"), f"unexpected {kind} time domain: {last_when}"
        return int(last_when[1:]) // per_sample

    return FadeState(
        in_active=region.get("fade-in-active") == "1",
        out_active=region.get("fade-out-active") == "1",
        in_samples=fade_samples("FadeIn"),
        out_samples=fade_samples("FadeOut"),
    )


def _saved_fade_state(ardour_session, mcp, expected: FadeState) -> FadeState:
    """Save the session and poll the file until it shows the expected fade state."""

    def read() -> FadeState:
        mcp.call("session_save")
        return _fade_state(ardour_session)

    return poll_until(read, lambda state: state == expected, interval=0.5)


FIXTURE_STATE = FadeState(True, True, FIXTURE_FADE_IN, FIXTURE_FADE_OUT)
CLEARED_STATE = FadeState(False, False, MIN_FADE, MIN_FADE)


@pytest.mark.parametrize(
    "ardour_session", [{"fixture": "audio-fades"}], indirect=True, ids=["forward-delete"]
)
def test_clear_fades_resets_both_fades_to_the_minimum(ardour_session, coverage_tracker) -> None:
    """S16-09. The Delete chord deactivates both fades and resets them to 64 samples.

    The profile binds the chord on both Primary-Level4-Delete and Primary-Level4-BackSpace
    (a Mac keyboard sends BackSpace for the key labelled delete; forward delete needs Fn).
    Only the Delete keyval can be exercised here: a synthetic BackSpace with any modifier
    flags never reaches Ardour's bindings -- posted via CGEventPostToPid or the session
    event tap alike -- while bare synthetic BackSpace and every modified arrow, letter and
    forward-delete chord in this suite arrive fine. The BackSpace variant therefore stays
    covered by the static expectation in tests/expectations.toml, and the shared Lua slot
    is what this test verifies behaviorally.
    """
    mcp = ardour_session.mcp()
    assert _fade_state(ardour_session) == FIXTURE_STATE, "fixture fades changed"

    try:
        ardour_session.focus_main_window()
        ardour_session.send_hotkey(KEY_A, FLAG_COMMAND)  # Editor/select-all-objects
        time.sleep(SETTLE)

        ardour_session.send_hotkey(KEY_FORWARD_DELETE, FLAG_COMMAND | FLAG_OPTION)
        assert _saved_fade_state(ardour_session, mcp, CLEARED_STATE) == CLEARED_STATE

        mcp.call("session_undo")
        assert _saved_fade_state(ardour_session, mcp, FIXTURE_STATE) == FIXTURE_STATE, (
            "undo must restore the original fade lengths and active states"
        )

        mcp.call("session_redo")
        assert _saved_fade_state(ardour_session, mcp, CLEARED_STATE) == CLEARED_STATE, (
            "redo must clear the fades again"
        )

        coverage_tracker["S16-09"]["e2e"] = "passed"
    except Exception:
        coverage_tracker["S16-09"]["e2e"] = "failed"
        _dump("S16-09-fades", vars(_fade_state(ardour_session)))
        raise


@pytest.mark.parametrize(
    "ardour_session", [{"fixture": "audio-fades"}], indirect=True, ids=["mixed"]
)
def test_clear_fades_skips_midi_regions_in_a_mixed_selection(
    ardour_session, coverage_tracker
) -> None:
    """S16-09. A selection containing a MIDI region must not fail or touch that region."""
    mcp = ardour_session.mcp()
    mcp.add_midi_region(REGION_START, REGION_END, name="Fades")
    midi_before = [
        track
        for track in mcp.region_state()
        if track["trackName"] and "Fades" in track["trackName"]
    ]
    assert midi_before and midi_before[0]["regions"], "MIDI region was not created"

    try:
        ardour_session.focus_main_window()
        # Twice on purpose: adding the track selects it asynchronously, and that event can
        # land after a single Cmd+A and replace the object selection it just made.
        for _ in range(2):
            ardour_session.send_hotkey(KEY_A, FLAG_COMMAND)  # selects the audio + MIDI regions
            time.sleep(SETTLE)

        ardour_session.send_hotkey(KEY_FORWARD_DELETE, FLAG_COMMAND | FLAG_OPTION)
        assert _saved_fade_state(ardour_session, mcp, CLEARED_STATE) == CLEARED_STATE, (
            "the audio region's fades must clear even with a MIDI region selected"
        )

        midi_after = [
            track
            for track in mcp.region_state()
            if track["trackName"] and "Fades" in track["trackName"]
        ]
        assert midi_after == midi_before, "the MIDI region must be untouched"

        coverage_tracker["S16-09"]["e2e"] = "passed"
    except Exception:
        coverage_tracker["S16-09"]["e2e"] = "failed"
        _dump("S16-09-mixed", vars(_fade_state(ardour_session)))
        raise


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
    # Sent twice on purpose. Selecting the same regions again is a no-op, and nothing on the
    # MCP surface reports the Editor selection, so there is no state to poll for; repeating
    # the key is the only way to stop a single slow or dropped dispatch from turning into a
    # duplicate that silently had nothing to work with.
    for _ in range(2):
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
