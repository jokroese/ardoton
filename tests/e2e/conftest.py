from __future__ import annotations

import pytest

from e2e.driver import create_isolated_session
from support import ARDOUR_BIN


@pytest.fixture
def ardour_session(tmp_path, request):
    if not ARDOUR_BIN.is_file():
        pytest.skip(f"Ardour not found at {ARDOUR_BIN}")

    from ApplicationServices import AXIsProcessTrusted

    if not AXIsProcessTrusted():
        pytest.fail(
            "macOS Accessibility permission is required for Ardour E2E tests. "
            "Enable Terminal/Cursor in System Settings → Privacy & Security → Accessibility.",
            pytrace=False,
        )

    session = create_isolated_session(tmp_path)
    try:
        session.launch()
        session.wait_for_main_window(timeout=90.0)
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
