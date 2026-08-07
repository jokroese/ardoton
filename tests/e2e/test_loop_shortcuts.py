"""Runtime coverage for the Phase 2 Lua loop shortcuts.

The loop family is the one group that can be driven end to end through the MCP HTTP
surface: markers_set_auto_loop_samples establishes a known range, the shortcut is sent
as a real key event, and markers_list reads the range back. Nothing here depends on an
Editor selection, which is what keeps the S16-11 case static-only.
"""

from __future__ import annotations

import json
import re
import time

import pytest

from e2e.driver import (
    FLAG_COMMAND,
    FLAG_CONTROL,
    FLAG_OPTION,
    KEY_DOWN,
    KEY_LEFT,
    KEY_RIGHT,
    KEY_UP,
)

pytestmark = [pytest.mark.e2e, pytest.mark.requires_ardour]

SAMPLE_RATE = 48000
LOOP_START = 10 * SAMPLE_RATE
LOOP_END = 14 * SAMPLE_RATE
LOOP_LENGTH = LOOP_END - LOOP_START

SETTLE = 1.0


def _dump(label: str, payload: object) -> None:
    """Write a payload to test-results and echo it, so a failing run is still informative."""
    from support import ensure_results_dir

    destination = ensure_results_dir() / "e2e" / f"{label}.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2, sort_keys=True)
    destination.write_text(text, encoding="utf-8")
    print(f"\n----- {label} -----\n{text}\n")


def test_probe_loop_shortcut(ardour_session) -> None:
    """Smoke test for the round trip, and a state dump for debugging the rest of the module.

    markers_list declares no outputSchema, so McpClient.loop_range() reads field names that
    were observed rather than specified. This dumps the payload on every run so a change in
    that shape shows up here first, with the data attached, rather than as a KeyError
    somewhere less obvious.
    """
    mcp = ardour_session.mcp()
    mcp.set_loop_range(LOOP_START, LOOP_END)
    time.sleep(SETTLE)
    _dump("probe-markers-before", mcp.markers())

    ardour_session.focus_main_window()
    ardour_session.send_hotkey(KEY_UP)
    time.sleep(SETTLE)
    _dump("probe-markers-after", mcp.markers())

    start, end = mcp.loop_range()
    assert (start, end) == (LOOP_START + LOOP_LENGTH, LOOP_END + LOOP_LENGTH), (
        "Up should move the loop forward by exactly its own length"
    )


@pytest.mark.parametrize(
    ("source_id", "label", "key", "flags", "expected"),
    [
        ("S08-09", "move-forward", KEY_UP, 0, (LOOP_START + LOOP_LENGTH, LOOP_END + LOOP_LENGTH)),
        ("S08-09", "move-back", KEY_DOWN, 0, (LOOP_START - LOOP_LENGTH, LOOP_END - LOOP_LENGTH)),
        (
            "S08-10",
            "double",
            KEY_UP,
            FLAG_COMMAND | FLAG_OPTION,
            (LOOP_START, LOOP_START + LOOP_LENGTH * 2),
        ),
        (
            "S08-10",
            "halve",
            KEY_DOWN,
            FLAG_COMMAND | FLAG_OPTION,
            (LOOP_START, LOOP_START + LOOP_LENGTH // 2),
        ),
    ],
)
def test_loop_length_shortcuts(
    ardour_session, coverage_tracker, source_id, label, key, flags, expected
) -> None:
    """Move-by-length and scale-length depend only on the loop itself, so they are exact."""
    mcp = ardour_session.mcp()
    mcp.set_loop_range(LOOP_START, LOOP_END)
    time.sleep(SETTLE)
    assert mcp.loop_range() == (LOOP_START, LOOP_END), "loop range was not established"

    try:
        ardour_session.focus_main_window()
        ardour_session.send_hotkey(key, flags)
        time.sleep(SETTLE)
        assert mcp.loop_range() == expected
        coverage_tracker[source_id]["e2e"] = "passed"
    except Exception:
        coverage_tracker[source_id]["e2e"] = "failed"
        _dump(f"{source_id}-{label}-markers", mcp.markers())
        raise


def _fixture_bar_samples() -> int:
    """One bar of the fixture session, in samples.

    The resize shortcut steps by a bar, so the expected distance is a property of the
    fixture's tempo map. Read it out of the session file rather than measuring it with the
    shortcut under test, and rather than hardcoding a number that silently stops matching if
    the fixture is ever re-saved at a different tempo.
    """
    from support import TESTS

    session = TESTS / "fixtures" / "session" / "baseline" / "Baseline.ardour"
    text = session.read_text(encoding="utf-8")

    tempos = re.findall(r'<Tempo npm="([0-9.]+)"[^>]*?note-type="([0-9.]+)"', text)
    meters = re.findall(r'<Meter note-value="([0-9.]+)" divisions-per-bar="([0-9.]+)"', text)
    assert len(tempos) == 1, f"expected a constant-tempo fixture, found {len(tempos)} tempos"
    assert len(meters) == 1, f"expected a single-meter fixture, found {len(meters)} meters"

    npm, note_type = (float(value) for value in tempos[0])
    note_value, divisions_per_bar = (float(value) for value in meters[0])

    # Quarter notes per minute, then the bar length in quarter notes -- the same expression
    # the script uses (EditingContext::get_a_grid_type_as_beats, GridTypeBar case).
    quarters_per_minute = npm * (4.0 / note_type)
    bar_quarters = (4.0 * divisions_per_bar) / note_value

    return round(bar_quarters / quarters_per_minute * 60.0 * SAMPLE_RATE)


BAR = _fixture_bar_samples()


@pytest.mark.parametrize(
    ("source_id", "label", "key", "flags", "moved_back"),
    [
        ("S08-07", "nudge-left", KEY_LEFT, FLAG_CONTROL, True),
        ("S08-08", "nudge-right", KEY_RIGHT, FLAG_CONTROL, False),
    ],
)
def test_nudge_shortcuts_slide_the_loop(
    ardour_session, coverage_tracker, source_id, label, key, flags, moved_back
) -> None:
    """Nudge moves by the nudge clock, whose value is a user preference.

    Asserting a specific distance would pin this to whatever the nudge clock happens to
    read, so this asserts direction and that the length survives.
    """
    mcp = ardour_session.mcp()
    mcp.set_loop_range(LOOP_START, LOOP_END)
    time.sleep(SETTLE)
    assert mcp.loop_range() == (LOOP_START, LOOP_END), "loop range was not established"

    try:
        ardour_session.focus_main_window()
        ardour_session.send_hotkey(key, flags)
        time.sleep(SETTLE)
        start, end = mcp.loop_range()

        assert end - start == LOOP_LENGTH, "nudge must not change loop length"
        assert (start < LOOP_START) if moved_back else (start > LOOP_START)

        coverage_tracker[source_id]["e2e"] = "passed"
    except Exception:
        coverage_tracker[source_id]["e2e"] = "failed"
        _dump(f"{source_id}-{label}-markers", mcp.markers())
        raise


@pytest.mark.parametrize(
    ("label", "key", "expected_end"),
    [
        ("shorten", KEY_LEFT, LOOP_END - BAR),
        ("lengthen", KEY_RIGHT, LOOP_END + BAR),
    ],
)
def test_resize_shortcuts_move_the_loop_end(
    ardour_session, coverage_tracker, label, key, expected_end
) -> None:
    """S08-11 and S16-12, which share slots 20/21. Only the end moves, by exactly one bar.

    The step used to be the nudge clock, a user preference defaulting to 5s, which made this
    a silent no-op on any loop of 5s or shorter and forced the test to measure the live nudge
    distance and size the loop around it. A bar is a property of the session's tempo map, so
    the distance is now known up front and asserted exactly.
    """
    mcp = ardour_session.mcp()
    mcp.set_loop_range(LOOP_START, LOOP_END)
    time.sleep(SETTLE)
    assert mcp.loop_range() == (LOOP_START, LOOP_END), "loop range was not established"

    try:
        ardour_session.focus_main_window()
        ardour_session.send_hotkey(key, FLAG_COMMAND | FLAG_OPTION)
        time.sleep(SETTLE)

        assert mcp.loop_range() == (LOOP_START, expected_end)

        coverage_tracker["S08-11"]["e2e"] = "passed"
        coverage_tracker["S16-12"]["e2e"] = "passed"
    except Exception:
        coverage_tracker["S08-11"]["e2e"] = "failed"
        coverage_tracker["S16-12"]["e2e"] = "failed"
        _dump(f"S08-11-{label}-markers", mcp.markers())
        raise


def test_loop_shortcuts_are_not_undoable(ardour_session) -> None:
    """Decision C, asserted rather than documented.

    Location edits cannot be registered on the undo stack from Lua, so Cmd+Z must not put
    the loop back where it was. If this test ever fails, undo became reachable and
    docs/installation.md plus the four script headers are wrong.

    What sits on top of the undo stack is the setup, not the shortcut:
    markers_set_auto_loop_samples creates the loop location as a reversible command. So the
    undo below reaches past the Lua edit and removes the location outright -- hence the
    None case. Were the Lua edit undoable it would be popped first and the pre-shortcut
    range would come back, which is exactly what this rules out.
    """
    mcp = ardour_session.mcp()
    mcp.set_loop_range(LOOP_START, LOOP_END)
    time.sleep(SETTLE)

    ardour_session.focus_main_window()
    ardour_session.send_hotkey(KEY_UP)
    time.sleep(SETTLE)
    moved = mcp.loop_range()
    assert moved != (LOOP_START, LOOP_END), "shortcut did not move the loop"

    mcp.call("session_undo")
    time.sleep(SETTLE)
    after = mcp.loop_range_or_none()
    assert after != (LOOP_START, LOOP_END), "loop edit unexpectedly became undoable"
    assert after in (None, moved), f"undo left the loop somewhere unexpected: {after}"
