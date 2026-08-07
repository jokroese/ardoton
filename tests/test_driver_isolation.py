"""Non-GUI coverage for the E2E driver's per-session isolation.

Nothing here launches Ardour. It checks the wiring that stops two concurrent E2E runs from
answering each other's requests, which is exactly the property a single-session E2E run
cannot demonstrate: the suite would pass just as happily with every session pointed at one
shared port.

The module name deliberately avoids "e2e"; the root conftest marks anything whose path
contains that substring as an E2E test.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

from e2e.driver import ArdourSession, free_localhost_port, mcp_url
from support import ROOT


def _session(tmp_path: Path, name: str) -> ArdourSession:
    root = tmp_path / name
    home = root / "home"
    session_dir = root / "sessions" / "baseline"
    return ArdourSession(
        root=root,
        home=home,
        config_dir=home / "Library" / "Preferences" / "Ardour9",
        session_dir=session_dir,
        session_file=session_dir / "Baseline.ardour",
    )


def test_sessions_get_distinct_mcp_ports_and_urls(tmp_path: Path) -> None:
    first = _session(tmp_path, "first")
    second = _session(tmp_path, "second")
    assert first.mcp_port != second.mcp_port
    assert first.mcp_url != second.mcp_url
    assert first.mcp_url == f"http://127.0.0.1:{first.mcp_port}/mcp"


def test_enable_mcp_writes_the_session_port(tmp_path: Path) -> None:
    session = _session(tmp_path, "ports")
    session.config_dir.mkdir(parents=True)
    (session.config_dir / "config").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<Config/>\n', encoding="utf-8"
    )

    session.enable_mcp()

    protocol = ET.parse(session.config_dir / "config").getroot().find("./ControlProtocols/Protocol")
    assert protocol is not None
    assert protocol.get("name") == "MCP HTTP Server (Experimental)"
    assert protocol.get("active") == "1"
    assert protocol.get("port") == str(session.mcp_port)


def test_free_localhost_port_varies_and_is_in_range() -> None:
    ports = {free_localhost_port() for _ in range(5)}
    assert len(ports) > 1, ports
    assert all(1024 < port <= 65535 for port in ports), ports


def test_mcp_url_targets_loopback_only() -> None:
    assert mcp_url(1234) == "http://127.0.0.1:1234/mcp"


def test_no_fixed_mcp_port_constant_remains() -> None:
    """A shared default would silently reintroduce the collision this removed.

    Matching an assignment rather than the bare number, so the comment explaining why 4820
    is avoided does not trip the check.
    """
    source = (ROOT / "tests" / "e2e" / "driver.py").read_text(encoding="utf-8")
    assert "MCP_PORT" not in source
    assert not re.search(r"=\s*4820\b", source), "driver still hardcodes Ardour's default port"
