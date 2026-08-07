from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

import pytest

from support import REAL_CONFIG, ROOT

pytestmark = [pytest.mark.installer]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _real_config_fingerprint() -> dict[str, str]:
    if not REAL_CONFIG.exists():
        return {}
    fingerprint: dict[str, str] = {}
    for path in sorted(REAL_CONFIG.rglob("*")):
        if path.is_file():
            rel = str(path.relative_to(REAL_CONFIG))
            fingerprint[rel] = _sha256(path)
    return fingerprint


def test_installer_macos_round_trip() -> None:
    before = _real_config_fingerprint()
    script = ROOT / "tests" / "test_installer_macos.sh"
    result = subprocess.run(
        ["/bin/zsh", str(script)],
        check=False,
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "macOS installer checks passed" in result.stdout
    after = _real_config_fingerprint()
    assert after == before, "installer test must not touch the real Ardour configuration"


def test_installer_never_targets_live_home_by_default_in_harness() -> None:
    """The shell harness always sets ARDOTON_CONFIG_DIR to a temp path."""
    source = (ROOT / "tests" / "test_installer_macos.sh").read_text(encoding="utf-8")
    assert "ARDOTON_CONFIG_DIR=" in source
    assert "mktemp" in source
