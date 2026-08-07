#!/usr/bin/env python3
"""Generate profile/ui-scripts/ardourton-actions.lua-state from profile/scripts/manifest.json.

Requires Ardour 9.7 installed locally: this shells out to Ardour's own bundled Lua build
(ardour9-lua) to compile each script's `factory` function and dump its bytecode, because
Ardour's action-script state format only accepts bytecode produced by Ardour's own Lua build
(see tests/test_lua_runtime.py::test_incompatible_action_state_fails). It cannot run in an
environment without Ardour 9.7 installed.

Before trusting this tool's output for new slots, run it with --check against the current
profile and confirm the result passes the checks in tests/check_lua.lua (via
`uv run pytest -m requires_ardour`), including that it reproduces the already-shipped slots
byte-for-byte.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "profile"
MANIFEST_PATH = PROFILE / "scripts" / "manifest.json"
SCRIPTS_DIR = PROFILE / "scripts"
ACTION_STATE_PATH = PROFILE / "ui-scripts" / "ardourton-actions.lua-state"
DUMP_SCRIPT = ROOT / "tools" / "dump_lua_action.lua"

ARDOUR_LUA = Path("/Applications/Ardour9.app/Contents/MacOS/ardour9-lua")


def load_manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def lua_literal(value: object) -> str:
    """Render a Python scalar as a Lua literal. Only covers the types our manifest uses."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, str):
        # Manifest strings are plain identifiers/short text in practice; escape defensively.
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    raise TypeError(f"unsupported param type for Lua literal: {type(value)!r}")


def params_literal(params: dict) -> str:
    if not params:
        return "{}"
    entries = ", ".join(
        f"[{lua_literal(key)}] = {lua_literal(value)}" for key, value in params.items()
    )
    return "{ " + entries + " }"


def dump_slot(ardour_lua: Path, entry: dict) -> str:
    script_path = SCRIPTS_DIR / entry["source"]
    args = [
        str(ardour_lua),
        str(DUMP_SCRIPT),
        str(script_path),
        str(entry["slot"]),
        entry["name"],
        params_literal(entry.get("params", {})),
    ]
    result = subprocess.run(args, capture_output=True, text=False, check=False)
    if result.returncode != 0:
        # ardour9-lua prints script failures as "Error: ..." on stdout, not stderr.
        detail = (result.stderr or result.stdout).decode("utf-8", errors="replace")
        raise RuntimeError(f"slot {entry['slot']} ({entry['source']}) failed to compile:\n{detail}")
    # dump_lua_action.lua emits ASCII-only text (\NNN escapes for bytecode bytes).
    try:
        fragment = result.stdout.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise RuntimeError(
            f"slot {entry['slot']} ({entry['source']}) emitted non-UTF-8 stdout; "
            r"dump_lua_action.lua must escape bytecode as \NNN decimal sequences"
        ) from exc
    if not fragment.strip():
        raise RuntimeError(f"slot {entry['slot']} ({entry['source']}) produced no output")
    if not fragment.lstrip().startswith(f"scripts[{entry['slot']}]"):
        raise RuntimeError(
            f"slot {entry['slot']} ({entry['source']}) produced unexpected stdout:\n"
            f"{fragment[:500]}"
        )
    return fragment


def build(ardour_lua: Path) -> str:
    manifest = load_manifest()
    slots = sorted(manifest["slots"], key=lambda entry: entry["slot"])
    fragments = [dump_slot(ardour_lua, entry) for entry in slots]
    return "".join(fragments)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--ardour-lua",
        type=Path,
        default=ARDOUR_LUA,
        help="path to Ardour's bundled ardour9-lua binary",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="print the generated fragment to stdout instead of writing it to the profile",
    )
    args = parser.parse_args()

    if not args.ardour_lua.is_file():
        print(f"error: ardour9-lua not found at {args.ardour_lua}", file=sys.stderr)
        print("Ardour 9.7 must be installed locally to run this tool.", file=sys.stderr)
        return 1

    try:
        content = build(args.ardour_lua)
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.check:
        sys.stdout.write(content)
        return 0

    ACTION_STATE_PATH.write_text(content, encoding="utf-8")
    print(f"wrote {ACTION_STATE_PATH.relative_to(ROOT)} ({len(content)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
