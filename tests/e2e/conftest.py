from __future__ import annotations

import pytest

from e2e.driver import create_isolated_session
from support import ARDOUR_BIN


@pytest.fixture
def ardour_session(tmp_path, request):
    """An isolated Ardour with the profile installed and the baseline session open.

    Parametrize indirectly with a dict to change the starting state, for example
    ``{"grid_type": "GridTypeBeatDiv4"}``. Only the temporary copy is touched; the
    repository fixture and the real configuration stay as they are.
    """
    if not ARDOUR_BIN.is_file():
        pytest.skip(f"Ardour not found at {ARDOUR_BIN}")

    from ApplicationServices import AXIsProcessTrusted

    if not AXIsProcessTrusted():
        pytest.fail(
            "macOS Accessibility permission is required for Ardour E2E tests. "
            "Enable Terminal/Cursor in System Settings → Privacy & Security → Accessibility.",
            pytrace=False,
        )

    options = dict(getattr(request, "param", None) or {})
    session = create_isolated_session(tmp_path, fixture=options.pop("fixture", "baseline"))
    grid_type = options.pop("grid_type", None)
    if grid_type is not None:
        session.set_editor_grid_type(grid_type)
    assert not options, f"unknown ardour_session options: {sorted(options)}"

    try:
        session.launch()
        session.wait_for_main_window(timeout=90.0)
        session.wait_until_ready()
        yield session
    except Exception:
        session.terminate()
        raise
    finally:
        session.terminate()
        try:
            session.assert_real_config_unchanged()
        except Exception as exc:
            request.node.add_report_section("call", "isolation", str(exc))
            raise


@pytest.fixture
def isolated_home_ready(tmp_path):
    """Prepare an isolated HOME + installed profile without launching Ardour."""
    if not ARDOUR_BIN.is_file():
        pytest.skip(f"Ardour not found at {ARDOUR_BIN}")
    session = create_isolated_session(tmp_path)
    yield session
    session.terminate()
    session.assert_real_config_unchanged()
