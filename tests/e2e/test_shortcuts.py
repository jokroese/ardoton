from __future__ import annotations

import time
import xml.etree.ElementTree as ET

import pytest

from e2e.driver import FLAG_COMMAND, FLAG_SHIFT, KEY_C, KEY_F9, KEY_T

pytestmark = [pytest.mark.e2e, pytest.mark.requires_ardour]


def _routes(session_file) -> list[dict[str, str]]:
    root = ET.parse(session_file).getroot()
    routes = []
    for route in root.findall(".//Route"):
        routes.append(route.attrib)
    return routes


def _new_route(before: list[dict[str, str]], after: list[dict[str, str]]) -> dict[str, str]:
    before_ids = {route["id"] for route in before}
    created = [route for route in after if route["id"] not in before_ids]
    assert len(created) == 1, (before, after)
    return created[0]


def _dump_failure(ardour_session, label: str) -> None:
    from support import RESULTS_DIR

    dest = RESULTS_DIR / "e2e" / f"{label}.png"
    try:
        ardour_session.capture_screenshot(dest)
    except Exception:
        pass


def test_cmd_t_adds_audio_track(ardour_session, coverage_tracker) -> None:
    before = _routes(ardour_session.session_file)
    try:
        ardour_session.focus_main_window()
        ardour_session.send_hotkey(KEY_T, FLAG_COMMAND)
        time.sleep(1.5)
        ardour_session.save_session_via_menu_action()
        time.sleep(1.0)
        after = _routes(ardour_session.session_file)
        assert _new_route(before, after)["default-type"] == "audio"
        coverage_tracker["S19-01"]["e2e"] = "passed"
    except Exception:
        coverage_tracker["S19-01"]["e2e"] = "failed"
        _dump_failure(ardour_session, "S19-01-cmd-t")
        raise


def test_cmd_shift_t_adds_midi_track(ardour_session, coverage_tracker) -> None:
    before = _routes(ardour_session.session_file)
    try:
        ardour_session.focus_main_window()
        ardour_session.send_hotkey(KEY_T, FLAG_COMMAND | FLAG_SHIFT)
        time.sleep(1.5)
        ardour_session.save_session_via_menu_action()
        time.sleep(1.0)
        after = _routes(ardour_session.session_file)
        assert _new_route(before, after)["default-type"] == "midi"
        coverage_tracker["S19-02"]["e2e"] = "passed"
    except Exception:
        coverage_tracker["S19-02"]["e2e"] = "failed"
        _dump_failure(ardour_session, "S19-02-cmd-shift-t")
        raise


def test_f9_starts_record_roll(ardour_session, coverage_tracker) -> None:
    try:
        # Ardour requires an armed track before entering record-roll.
        ardour_session.send_hotkey(KEY_T, FLAG_COMMAND)
        time.sleep(1.5)
        ardour_session.send_hotkey(KEY_C)
        time.sleep(0.5)
        ardour_session.send_hotkey(KEY_F9)
        state = ardour_session.mcp().transport_state()
        # The Dummy backend does not process transport cycles, but Ardour
        # reports the requested record-roll speed immediately.
        assert state["speed"] == 1, state
        coverage_tracker["S20-06"]["e2e"] = "passed"
    except Exception:
        coverage_tracker["S20-06"]["e2e"] = "failed"
        _dump_failure(ardour_session, "S20-06-f9")
        raise


# S16-11 remains static-only. Cmd+L needs a real Editor time selection; neither
# native start/finish-range actions nor mouse drags establish one under the
# Dummy backend. Continue with a fixture that persists an Editor selection, or
# an Ardour MCP API that creates and reads editor selections plus loop state.
