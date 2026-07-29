from __future__ import annotations

import time
import xml.etree.ElementTree as ET

import pytest

from e2e.driver import FLAG_COMMAND, FLAG_SHIFT, KEY_T

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
        coverage_tracker["S03"]["e2e"] = "passed"
    except Exception:
        coverage_tracker["S03"]["e2e"] = "failed"
        _dump_failure(ardour_session, "S03-cmd-t")
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
        coverage_tracker["S04"]["e2e"] = "passed"
    except Exception:
        coverage_tracker["S04"]["e2e"] = "failed"
        _dump_failure(ardour_session, "S04-cmd-shift-t")
        raise

