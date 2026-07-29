from __future__ import annotations

from PIL import Image

from e2e.test_visuals import _compare


def test_visual_comparison_accepts_identical_rgb_images(tmp_path) -> None:
    expected = tmp_path / "expected.png"
    actual = tmp_path / "actual.png"
    Image.new("RGB", (32, 32), "white").save(expected)
    Image.new("RGB", (32, 32), "white").save(actual)

    _compare(expected, actual, tmp_path / "diff.png")
