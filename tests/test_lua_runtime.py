from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from support import ACTION_STATE_PATH, ARDOUR_LUA, PROFILE, ROOT, TESTS

pytestmark = [pytest.mark.requires_ardour]


def _ardour_lua() -> Path:
    if not ARDOUR_LUA.is_file():
        pytest.skip(f"Ardour Lua runtime not found: {ARDOUR_LUA}")
    return ARDOUR_LUA


def _lua_version(executable: Path) -> str:
    result = subprocess.run(
        [str(executable), "--version"],
        check=False,
        capture_output=True,
        text=True,
    )
    return (result.stdout + result.stderr).strip()


def test_ardour_lua_reports_9_7() -> None:
    version = _lua_version(_ardour_lua())
    assert re.search(r"9\.7", version), version


def test_check_lua_passes_against_profile() -> None:
    executable = _ardour_lua()
    result = subprocess.run(
        [str(executable), str(TESTS / "check_lua.lua"), str(PROFILE)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Lua checks passed" in result.stdout


def _run_build_tool(*flags: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools" / "build_lua_actions.py"),
            *flags,
            "--ardour-lua",
            str(_ardour_lua()),
        ],
        check=False,
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )


def test_action_state_reproduces_from_scripts() -> None:
    """The committed bytecode must regenerate byte-for-byte from the committed scripts.

    string.dump keeps linedefined/lastlinedefined even when stripping debug info, so editing
    a script's header comment changes its bytecode. Without this check the action state can
    silently stop matching the sources it was built from. --check owns the comparison; this
    only asserts its verdict and that it did not rewrite the tracked file.
    """
    tracked_before = ACTION_STATE_PATH.read_bytes()
    result = _run_build_tool("--check")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "matches its sources" in result.stdout
    assert ACTION_STATE_PATH.read_bytes() == tracked_before, "--check must never write"


def test_check_mode_reports_a_mismatch(tmp_path: Path) -> None:
    """--check must fail, name the file, and leave it untouched when sources drift."""
    del tmp_path
    tracked_before = ACTION_STATE_PATH.read_bytes()
    try:
        ACTION_STATE_PATH.write_bytes(tracked_before + b"\n-- drift\n")
        result = _run_build_tool("--check")
        assert result.returncode != 0
        assert "does not match its sources" in result.stderr
        assert ACTION_STATE_PATH.read_bytes() == tracked_before + b"\n-- drift\n"
    finally:
        ACTION_STATE_PATH.write_bytes(tracked_before)


def test_stdout_mode_emits_the_fragment() -> None:
    result = _run_build_tool("--stdout")
    assert result.returncode == 0, result.stderr
    assert result.stdout == ACTION_STATE_PATH.read_text(encoding="utf-8")


def test_incompatible_action_state_fails(tmp_path: Path) -> None:
    """Bytecode from system Lua (or a corrupt payload) must be rejected by ardour9-lua."""
    executable = _ardour_lua()
    fixture_profile = tmp_path / "profile"
    shutil.copytree(PROFILE, fixture_profile)

    # Replace action state with Lua source that system lua can parse but that
    # embeds invalid binary for Ardour's loader when load(..., "b") is used.
    bad_state = fixture_profile / "ui-scripts" / "ardoton-actions.lua-state"
    # Valid Lua text that defines scripts[28] with non-bytecode string as f.
    bad_state.write_text(
        'scripts[28] = { n = "Bad", a = {}, f = "not-bytecode", s = "" }\n'
        'scripts[29] = { n = "Bad", a = {}, f = "not-bytecode", s = "" }\n'
        'scripts[30] = { n = "Bad", a = {}, f = "not-bytecode", s = "" }\n'
        'scripts[31] = { n = "Bad", a = {}, f = "not-bytecode", s = "" }\n'
        'scripts[32] = { n = "Bad", a = {}, f = "not-bytecode", s = "" }\n',
        encoding="utf-8",
    )

    result = subprocess.run(
        [str(executable), str(TESTS / "check_lua.lua"), str(fixture_profile)],
        check=False,
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    assert result.returncode != 0
    combined = result.stdout + result.stderr
    assert re.search(r"action|slot|bytecode|invalid|attempt", combined, re.I), combined
