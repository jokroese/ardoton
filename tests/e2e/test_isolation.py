from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from e2e.driver import (
    ArdourSession,
    DriverError,
    create_isolated_session,
    fingerprint_tree,
)
from support import REAL_CONFIG, RESULTS_DIR

pytestmark = [pytest.mark.e2e, pytest.mark.requires_ardour]


def test_driver_refuses_live_config(tmp_path: Path) -> None:
    session = create_isolated_session(tmp_path)
    session.config_dir = REAL_CONFIG
    with pytest.raises(DriverError, match="live Ardour configuration"):
        session.ensure_safe_config_dir()


def test_driver_refuses_config_outside_temp_root(tmp_path: Path) -> None:
    session = create_isolated_session(tmp_path)
    session.config_dir = Path("/tmp/not-under-session-root/Ardour9")
    with pytest.raises(DriverError, match="outside the temporary test root"):
        session.ensure_safe_config_dir()


def test_focus_activates_ardour_application(monkeypatch, tmp_path: Path) -> None:
    activated = []
    raised = []

    class Application:
        def activateWithOptions_(self, options):
            activated.append(options)
            return True

    application = Application()
    monkeypatch.setitem(
        sys.modules,
        "AppKit",
        SimpleNamespace(
            NSApplicationActivateIgnoringOtherApps=1,
            NSRunningApplication=SimpleNamespace(
                runningApplicationWithProcessIdentifier_=lambda pid: application
            ),
        ),
    )
    monkeypatch.setitem(
        sys.modules,
        "ApplicationServices",
        SimpleNamespace(
            AXUIElementPerformAction=lambda window, action: raised.append((window, action)),
            kAXRaiseAction="raise",
        ),
    )
    session = ArdourSession(
        root=tmp_path,
        home=tmp_path / "home",
        config_dir=tmp_path / "config",
        session_dir=tmp_path / "session",
        session_file=tmp_path / "session" / "test.ardour",
        process=SimpleNamespace(pid=123),
    )
    monkeypatch.setattr(session, "wait_for_main_window", lambda timeout: "Ardour")

    session.focus_main_window()

    assert activated == [1]
    assert raised == [("Ardour", "raise")]


def test_hotkey_is_posted_directly_to_ardour(monkeypatch, tmp_path: Path) -> None:
    posted = []
    events = []
    quartz = SimpleNamespace(
        CGEventCreateKeyboardEvent=lambda source, key, down: events.append(
            {"key": key, "down": down}
        )
        or events[-1],
        CGEventPostToPid=lambda pid, event: posted.append((pid, event.copy())),
        CGEventSetFlags=lambda event, flags: event.update(flags=flags),
    )
    monkeypatch.setitem(sys.modules, "Quartz", quartz)
    session = ArdourSession(
        root=tmp_path,
        home=tmp_path / "home",
        config_dir=tmp_path / "config",
        session_dir=tmp_path / "session",
        session_file=tmp_path / "session" / "test.ardour",
        process=SimpleNamespace(pid=123),
    )
    monkeypatch.setattr(session, "focus_main_window", lambda: None)

    session.send_hotkey(17, 1 << 20)

    assert posted == [
        (123, {"key": 17, "down": True, "flags": 1 << 20}),
        (123, {"key": 17, "down": False, "flags": 1 << 20}),
    ]


def test_prepared_session_has_one_interchange_root(tmp_path: Path) -> None:
    session = create_isolated_session(tmp_path)

    roots = [path.name for path in (session.session_dir / "interchange").iterdir()]

    assert roots == ["baseline"]


def test_isolation_launch_screenshot_and_cleanup(tmp_path: Path) -> None:
    from ApplicationServices import AXIsProcessTrusted

    if not AXIsProcessTrusted():
        pytest.fail(
            "macOS Accessibility permission is required for Ardour E2E tests. "
            "Enable Terminal/Cursor in System Settings → Privacy & Security → Accessibility.",
            pytrace=False,
        )

    before = fingerprint_tree(REAL_CONFIG)
    session = create_isolated_session(tmp_path)
    shot = RESULTS_DIR / "e2e" / "isolation.png"
    try:
        session.launch()
        session.wait_for_main_window(timeout=90.0)
        session.capture_screenshot(shot)
        assert shot.is_file() and shot.stat().st_size > 0
    finally:
        pid = session.process.pid if session.process else None
        session.terminate()
        if pid is not None:
            try:
                os.kill(pid, 0)
                alive = True
            except OSError:
                alive = False
            assert not alive, f"Ardour PID {pid} still running after terminate"

    after = fingerprint_tree(REAL_CONFIG)
    assert after == before
