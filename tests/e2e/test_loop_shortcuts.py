"""Runtime coverage for the Phase 2 Lua loop shortcuts.

The loop family is the one group that can be driven end to end through the MCP HTTP
surface: markers_set_auto_loop_samples establishes a known range, the shortcut is sent
as a real key event, and markers_list reads the range back. Nothing here depends on an
Editor selection, which is what keeps the S16-11 case static-only.
"""

from __future__ import annotations

import json
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


def _measure_nudge_distance(ardour_session, mcp) -> int:
    """The live nudge-clock distance in samples, read back from one whole-loop nudge.

    The nudge clock is a user preference (Ardour defaults it to 5 seconds), so a test that
    needs to know how far a nudge reaches has to measure it rather than assume a value.
    """
    mcp.set_loop_range(LOOP_START, LOOP_END)
    time.sleep(SETTLE)
    ardour_session.focus_main_window()
    ardour_session.send_hotkey(KEY_RIGHT, FLAG_CONTROL)
    time.sleep(SETTLE)
    start, _ = mcp.loop_range()
    distance = start - LOOP_START
    assert distance > 0, f"nudge-right did not move the loop forward: start={start}"
    return distance


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
    ("label", "key", "shorter"),
    [
        ("shorten", KEY_LEFT, True),
        ("lengthen", KEY_RIGHT, False),
    ],
)
def test_resize_shortcuts_move_the_loop_end(
    ardour_session, coverage_tracker, label, key, shorter
) -> None:
    """S08-11. Only the end moves, and it moves by one nudge.

    Location::set_end rejects an end at or before the start, so a shorten only lands on a
    loop that is longer than one nudge -- and Ardour's default nudge (5s) is longer than the
    4s loop the other cases use. Measure the live nudge distance first and size the loop
    around it, so this tests the script rather than the nudge-clock preference.
    """
    mcp = ardour_session.mcp()
    nudge = _measure_nudge_distance(ardour_session, mcp)
    loop_end = LOOP_START + max(LOOP_LENGTH, nudge * 2)
    mcp.set_loop_range(LOOP_START, loop_end)
    time.sleep(SETTLE)
    assert mcp.loop_range() == (LOOP_START, loop_end), "loop range was not established"

    try:
        ardour_session.focus_main_window()
        ardour_session.send_hotkey(key, FLAG_COMMAND | FLAG_OPTION)
        time.sleep(SETTLE)
        start, end = mcp.loop_range()

        assert start == LOOP_START, "resize must leave the loop start alone"
        assert (end < loop_end) if shorter else (end > loop_end)

        coverage_tracker["S08-11"]["e2e"] = "passed"
    except Exception:
        coverage_tracker["S08-11"]["e2e"] = "failed"
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
