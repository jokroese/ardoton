"""Visual regression helpers and tests for canonical Ardour GUI states."""

from __future__ import annotations

import time
from pathlib import Path

import pytest
from PIL import Image, ImageChops, ImageDraw, ImageStat

from support import RESULTS_DIR, TESTS

pytestmark = [pytest.mark.e2e, pytest.mark.visual, pytest.mark.requires_ardour]

SNAPSHOT_DIR = TESTS / "snapshots" / "macos"

# Regions ignored during comparison (clocks, meters, playhead-ish strips),
# expressed as fractions of the normalized screenshot dimensions.
DYNAMIC_MASKS = [
    # transport clocks / toolbar strip
    (0, 0, 1, 48 / 900),
    # right-edge meters approximation
    (1380 / 1440, 48 / 900, 1, 1),
]


def _apply_masks(image: Image.Image) -> Image.Image:
    masked = image.convert("RGB")
    draw = ImageDraw.Draw(masked)
    width, height = masked.size
    for left, top, right, bottom in DYNAMIC_MASKS:
        draw.rectangle(
            (left * width, top * height, right * width, bottom * height),
            fill=(0, 0, 0),
        )
    return masked


def _compare(expected: Path, actual: Path, diff_path: Path, threshold: float = 2.0) -> None:
    exp = Image.open(expected).convert("RGB")
    act = Image.open(actual).convert("RGB")
    if exp.size != act.size:
        act = act.resize(exp.size)
    exp = _apply_masks(exp)
    act = _apply_masks(act)
    diff = ImageChops.difference(exp, act)
    # Mean absolute channel difference.
    mean = sum(ImageStat.Stat(diff).mean) / len(diff.getbands())
    if mean > threshold:
        diff_path.parent.mkdir(parents=True, exist_ok=True)
        exp.save(diff_path.parent / "expected.png")
        act.save(diff_path.parent / "actual.png")
        diff.save(diff_path)
        raise AssertionError(
            f"Visual diff mean={mean:.3f} exceeds threshold={threshold}; wrote {diff_path.parent}"
        )


def _ensure_or_compare(
    name: str,
    actual: Path,
    update: bool,
) -> None:
    expected = SNAPSHOT_DIR / f"{name}.png"
    out_dir = RESULTS_DIR / "visual" / name
    if update or not expected.exists():
        if not update and not expected.exists():
            raise AssertionError(
                f"Missing approved snapshot {expected}. "
                "Re-run with: uv run pytest -m visual --update-snapshots"
            )
        expected.parent.mkdir(parents=True, exist_ok=True)
        Image.open(actual).save(expected)
        return
    _compare(expected, actual, out_dir / "diff.png")


def test_editor_snapshot(ardour_session, update_snapshots) -> None:
    ardour_session.focus_main_window()
    time.sleep(1.0)
    actual = RESULTS_DIR / "visual" / "editor" / "capture.png"
    ardour_session.capture_screenshot(actual)
    _ensure_or_compare("editor", actual, update_snapshots)


def test_mixer_snapshot(ardour_session, update_snapshots) -> None:
    # Window → Mixer is typically Cmd+2 on Ardour; key code 19 = 2
    from Quartz import kCGEventFlagMaskCommand

    ardour_session.focus_main_window()
    ardour_session.send_hotkey(19, kCGEventFlagMaskCommand)
    time.sleep(1.0)
    actual = RESULTS_DIR / "visual" / "mixer" / "capture.png"
    ardour_session.capture_screenshot(actual)
    _ensure_or_compare("mixer", actual, update_snapshots)


def test_cues_snapshot(ardour_session, update_snapshots) -> None:
    # Cue / grid workspace often Cmd+3 or Tab; use Tab once toward cues if available.
    from e2e.driver import KEY_TAB

    ardour_session.focus_main_window()
    ardour_session.send_hotkey(KEY_TAB, 0)
    time.sleep(1.0)
    actual = RESULTS_DIR / "visual" / "cues" / "capture.png"
    ardour_session.capture_screenshot(actual)
    _ensure_or_compare("cues", actual, update_snapshots)


def test_beat_production_theme_present_snapshot(ardour_session, update_snapshots) -> None:
    # Theme activation is via installed color-file; capture editor as beat-production baseline.
    ardour_session.focus_main_window()
    time.sleep(1.0)
    actual = RESULTS_DIR / "visual" / "beat-production" / "capture.png"
    ardour_session.capture_screenshot(actual)
    _ensure_or_compare("beat-production", actual, update_snapshots)
