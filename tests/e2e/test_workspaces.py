from __future__ import annotations

import time

import pytest

from e2e.driver import KEY_TAB

pytestmark = [pytest.mark.e2e, pytest.mark.requires_ardour]


def test_tab_and_shift_tab_cycle_without_crash(ardour_session) -> None:
    ardour_session.focus_main_window()
    for _ in range(3):
        ardour_session.send_hotkey(KEY_TAB, 0)
        time.sleep(0.3)
        ardour_session.send_hotkey(KEY_TAB, 1 << 17)  # shift
        time.sleep(0.3)
    assert ardour_session.process is not None
    assert ardour_session.process.poll() is None


def test_theme_file_installed_in_isolated_config(isolated_home_ready) -> None:
    theme = isolated_home_ready.config_dir / "themes" / "ardoton-ardour.colors"
    assert theme.is_file()
    text = theme.read_text(encoding="utf-8")
    assert 'theme-name="Ardoton"' in text


def test_keymap_installed_as_ardoton_macos(isolated_home_ready) -> None:
    keys = isolated_home_ready.config_dir / "ardour.keys"
    assert keys.is_file()
    assert 'BindingSet name="Ardoton macOS"' in keys.read_text(encoding="utf-8")
