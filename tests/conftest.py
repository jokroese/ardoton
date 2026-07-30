from __future__ import annotations

import json
from pathlib import Path

import pytest

from support import (
    RESULTS_DIR,
    ROOT,
    ensure_results_dir,
    load_expectations,
)


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--update-snapshots",
        action="store_true",
        default=False,
        help="Overwrite approved visual snapshots (requires explicit opt-in).",
    )


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return ROOT


@pytest.fixture(scope="session")
def update_snapshots(request: pytest.FixtureRequest) -> bool:
    return bool(request.config.getoption("--update-snapshots"))


@pytest.fixture(scope="session")
def coverage_tracker() -> dict[str, dict[str, str]]:
    from support import shortcut_sources

    coverage: dict[str, dict[str, str]] = {
        feature_id: {"static": "not-covered", "e2e": "not-covered"}
        for feature_id in sorted(shortcut_sources())
    }
    bindings, _ = load_expectations()
    for binding in bindings:
        coverage.setdefault(
            binding.source_id,
            {"static": "not-covered", "e2e": "not-covered"},
        )
    return coverage


@pytest.fixture(scope="session", autouse=True)
def write_coverage_report(coverage_tracker: dict[str, dict[str, str]]):
    yield
    ensure_results_dir()
    path = RESULTS_DIR / "feature-coverage.json"
    path.write_text(
        json.dumps(coverage_tracker, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    del config
    for item in items:
        if "e2e" in str(item.fspath) or "/e2e/" in str(getattr(item, "path", "")):
            item.add_marker(pytest.mark.e2e)
