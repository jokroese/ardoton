from __future__ import annotations

import os
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from e2e.driver import create_isolated_session
from support import ARDOUR_BIN, ROOT

pytestmark = [pytest.mark.e2e, pytest.mark.requires_ardour]


def _count_routes(session_file: Path) -> int:
    root = ET.parse(session_file).getroot()
    return len(root.findall(".//Route"))


def test_fixture_session_has_master_route() -> None:
    session_file = (
        ROOT / "tests" / "fixtures" / "session" / "baseline" / "Baseline.ardour"
    )
    assert session_file.is_file()
    names = [
        route.get("name")
        for route in ET.parse(session_file).getroot().findall(".//Route")
    ]
    assert any(name and "Master" in name for name in names)


def test_beat_production_script_is_installed(isolated_home_ready) -> None:
    script = (
        isolated_home_ready.config_dir
        / "scripts"
        / "ardourton_beat_production.lua"
    )
    assert script.is_file()
    text = script.read_text(encoding="utf-8")
    assert "SessionInit" in text or "session" in text.lower()


def test_new_session_can_be_created_in_isolation(tmp_path: Path) -> None:
    """Create a fresh empty session under the disposable HOME without GUI."""
    session = create_isolated_session(tmp_path)
    target = session.root / "sessions" / "fresh"
    helper = ARDOUR_BIN.parent / "ardour9-new_session"
    env = os.environ.copy()
    env["HOME"] = str(session.home)
    result = subprocess.run(
        [str(helper), "-s", "48000", "-m", "2", str(target), "Fresh"],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    session_file = target / "Fresh.ardour"
    assert session_file.is_file()
    assert _count_routes(session_file) >= 1
    session.assert_real_config_unchanged()
