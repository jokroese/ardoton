"""Isolated Ardour GUI driver for macOS E2E tests."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import signal
import socket
import subprocess
import time
import urllib.request
import xml.etree.ElementTree as ET
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from support import ARDOUR_BIN, REAL_CONFIG, ROOT, TESTS

WINDOW_WIDTH = 1440
WINDOW_HEIGHT = 900


def free_localhost_port() -> int:
    """A localhost TCP port that is free right now.

    Ardour's MCP surface defaults to 4820 for everyone, so two E2E runs sharing this machine
    would answer each other's requests. Binding port 0 lets the OS pick from the ephemeral
    range, which it does not hand out again immediately, so the gap between closing this
    socket and Ardour binding the port is not a practical collision risk.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def mcp_url(port: int) -> str:
    """The endpoint MCPHttp serves (../ardour@9.7:libs/surfaces/mcp_http/mcp_http.cc:180)."""
    return f"http://127.0.0.1:{port}/mcp"


def _numeric_first(value: str) -> tuple[int, int, str]:
    """Sort key that orders Ardour's numeric string IDs by value, not lexically."""
    return (0, int(value), "") if value.isdigit() else (1, 0, value)


def poll_until[T](
    read: Callable[[], T],
    predicate: Callable[[T], bool],
    timeout: float = 10.0,
    interval: float = 0.25,
) -> T:
    """Read repeatedly until the predicate holds, and return the last value either way.

    Ardour applies most of these edits on its own GUI thread, so the state a test wants is
    usually there within a few milliseconds but occasionally is not. Callers keep their own
    assertion on the returned value; this only decides how long to wait, and it replaces
    both the immediate read that assumed the edit had landed and the fixed sleeps that
    assumed it would within a second.
    """
    deadline = time.monotonic() + timeout
    value = read()
    while not predicate(value) and time.monotonic() < deadline:
        time.sleep(interval)
        value = read()
    return value


class DriverError(RuntimeError):
    pass


class AccessibilityPermissionError(DriverError):
    pass


class McpClient:
    def __init__(self, port: int, pid: int | None = None) -> None:
        self.port = port
        self.pid = pid
        self.request_id = 0
        self._request(
            "initialize",
            {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "ardourton-e2e", "version": "1"},
            },
        )

    def call(self, tool: str, arguments: dict | None = None) -> dict:
        """Invoke any MCP tool and return its structuredContent."""
        result = self._request("tools/call", {"name": tool, "arguments": arguments or {}})
        return result.get("structuredContent", result)

    def transport_state(self) -> dict:
        return self.call("transport_get_state")

    def set_loop_range(self, start_sample: int, end_sample: int) -> dict:
        return self.call(
            "markers_set_auto_loop_samples",
            {"startSample": start_sample, "endSample": end_sample},
        )

    def markers(self) -> list[dict]:
        return self.call("markers_list").get("markers", [])

    def loop_range_or_none(self) -> tuple[int, int] | None:
        """Start and end of the auto-loop location, or None when the session has no loop.

        markers_list declares no outputSchema; these field names come from an observed
        payload (test-results/e2e/probe-markers-*.json), not from the schema.
        """
        for marker in self.markers():
            if marker.get("isAutoLoop"):
                return (
                    int(marker["locationStartSample"]),
                    int(marker["locationEndSample"]),
                )
        return None

    def loop_range(self) -> tuple[int, int]:
        found = self.loop_range_or_none()
        if found is None:
            raise DriverError(f"no auto-loop location in markers_list: {self.markers()}")
        return found

    def tracks(self, include_buses: bool = False) -> list[dict]:
        """Routes from tracks_list, without the buses by default.

        tracks_list reports the Master bus alongside real tracks, and the region tools
        reject a bus with "Route is not a track", so anything that reads regions has to
        filter first. Observed type values: "bus", "midi_track", "audio_track".
        """
        routes = self.call("tracks_list").get("tracks", [])
        if include_buses:
            return routes
        return [route for route in routes if route.get("type") != "bus"]

    def add_midi_track(self, name: str) -> str:
        """Create one MIDI track and return its route ID."""
        before = {str(route.get("id")) for route in self.tracks()}
        self.call("tracks_add", {"type": "midi", "count": 1, "name": name})
        added = [route for route in self.tracks() if str(route.get("id")) not in before]
        if not added:
            raise DriverError(f"tracks_add did not add a track: {self.tracks(include_buses=True)}")
        return str(added[0]["id"])

    def add_midi_region_to(
        self, track_id: str, start_sample: int, end_sample: int, name: str
    ) -> dict:
        created = self.call(
            "midi_region_add_samples",
            {
                "trackId": track_id,
                "startSample": start_sample,
                "endSample": end_sample,
                "name": name,
            },
        )
        return created.get("created", created)

    def add_midi_region(
        self, start_sample: int, end_sample: int, name: str = "Probe"
    ) -> tuple[str, dict]:
        """Add a MIDI track holding one empty region; return (trackId, created region).

        The baseline fixture session contains nothing but the Master bus, so a test that
        needs material has to make its own. It is MIDI because the MCP surface has no audio
        import tool -- there is no way to conjure an audio region from here.
        """
        track_id = self.add_midi_track(name)
        created = self.add_midi_region_to(track_id, start_sample, end_sample, f"{name}Region")
        return track_id, created

    def region_state(self) -> list[dict]:
        """Per-track region layout, reduced to the fields an assertion can rely on.

        track_get_regions also reports playlist IDs, BBT positions, lock/mute/hidden flags
        and a type discriminator. Comparing the whole payload would turn every assertion
        into a snapshot of unrelated Ardour internals, so this keeps identity (track and
        region ID, name) and extent (start and end sample) and drops the rest. Ordering is
        normalized because the region order in the payload follows playlist internals.
        """
        state: list[dict] = []
        for track in self.tracks():
            track_id = str(track["id"])
            payload = self.call("track_get_regions", {"id": track_id})
            state.append(
                {
                    "trackId": track_id,
                    "trackName": track.get("name"),
                    "regions": sorted(
                        (
                            {
                                "regionId": str(region["regionId"]),
                                "name": region["name"],
                                "start": int(region["startSample"]),
                                "end": int(region["endSample"]),
                            }
                            for region in payload.get("regions", [])
                        ),
                        key=lambda region: (region["start"], region["end"], region["name"]),
                    ),
                }
            )
        return sorted(state, key=lambda track: _numeric_first(track["trackId"]))

    @property
    def url(self) -> str:
        return mcp_url(self.port)

    def _request(self, method: str, params: dict) -> dict:
        self.request_id += 1
        payload = json.dumps(
            {"jsonrpc": "2.0", "id": self.request_id, "method": method, "params": params}
        ).encode()
        request = urllib.request.Request(
            self.url,
            payload,
            {"Content-Type": "application/json", "Accept": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                body = json.load(response)
        except OSError as exc:
            raise DriverError(
                f"MCP request {method!r} to {self.url} (Ardour pid {self.pid}) failed: {exc}"
            ) from exc
        if "error" in body:
            raise DriverError(str(body["error"]))
        return body["result"]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fingerprint_tree(root: Path) -> dict[str, str]:
    if not root.exists():
        return {}
    out: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            out[str(path.relative_to(root))] = _sha256(path)
    return out


def check_accessibility_permission() -> None:
    try:
        from ApplicationServices import AXIsProcessTrusted
    except ImportError as exc:  # pragma: no cover
        raise AccessibilityPermissionError(
            "PyObjC ApplicationServices is required for E2E tests."
        ) from exc

    if not AXIsProcessTrusted():
        raise AccessibilityPermissionError(
            "macOS Accessibility permission is required for Ardour E2E tests. "
            "Enable Terminal/Cursor in System Settings → Privacy & Security → Accessibility."
        )


@dataclass
class ArdourSession:
    root: Path
    home: Path
    config_dir: Path
    session_dir: Path
    session_file: Path
    process: subprocess.Popen | None = None
    real_config_before: dict[str, str] | None = None
    mcp_port: int = field(default_factory=free_localhost_port)

    @property
    def mcp_url(self) -> str:
        return mcp_url(self.mcp_port)

    def enable_mcp(self) -> None:
        config_path = self.config_dir / "config"
        config = ET.parse(config_path)
        protocols = ET.SubElement(config.getroot(), "ControlProtocols")
        # MCPHttp::set_state reads "port" off the Protocol node and falls back to the 4820
        # default (../ardour@9.7:libs/surfaces/mcp_http/mcp_http.cc:75;104-110).
        ET.SubElement(
            protocols,
            "Protocol",
            name="MCP HTTP Server (Experimental)",
            active="1",
            config="",
            port=str(self.mcp_port),
        )
        config.write(config_path, encoding="utf-8", xml_declaration=True)

    def mcp(self) -> McpClient:
        pid = self.process.pid if self.process is not None else None
        last_error: Exception | None = None
        for _ in range(10):
            try:
                return McpClient(self.mcp_port, pid)
            except Exception as exc:
                last_error = exc
                time.sleep(0.25)
        raise DriverError(
            f"MCP HTTP server did not start on 127.0.0.1:{self.mcp_port} "
            f"(Ardour pid {pid}): {last_error}"
        )

    def ensure_safe_config_dir(self) -> None:
        resolved = self.config_dir.resolve()
        root = self.root.resolve()
        if resolved == REAL_CONFIG.resolve():
            raise DriverError("Refusing to target the live Ardour configuration.")
        try:
            resolved.relative_to(root)
        except ValueError as exc:
            raise DriverError(
                f"Refusing to use config directory outside the temporary test root: {resolved}"
            ) from exc

    def install_profile(self) -> None:
        self.ensure_safe_config_dir()
        env = os.environ.copy()
        env["ARDOURTON_CONFIG_DIR"] = str(self.config_dir)
        env["ARDOURTON_SKIP_PROCESS_CHECK"] = "1"
        env["ARDOURTON_SKIP_VERSION_CHECK"] = "1"
        result = subprocess.run(
            ["/bin/zsh", str(ROOT / "installer" / "macos.sh"), "install"],
            check=False,
            capture_output=True,
            text=True,
            env=env,
            cwd=str(ROOT),
        )
        if result.returncode != 0:
            raise DriverError(result.stdout + result.stderr)

    def seed_config(self) -> None:
        self.ensure_safe_config_dir()
        self.config_dir.mkdir(parents=True, exist_ok=True)
        sessions_parent = self.root / "Music"
        sessions_parent.mkdir(parents=True, exist_ok=True)

        config_src = (TESTS / "fixtures" / "config" / "config.xml").read_text(encoding="utf-8")
        config_src = config_src.replace("SESSIONS_PLACEHOLDER", str(sessions_parent))
        (self.config_dir / "config").write_text(config_src, encoding="utf-8")

        shutil.copyfile(
            TESTS / "fixtures" / "config" / "ui_config.xml",
            self.config_dir / "ui_config",
        )
        # Empty ActionScript shell so installer can append.
        import base64

        encoded = base64.b64encode(b"scripts = {}\n").decode("ascii")
        (self.config_dir / "ui_scripts").write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            "<UIScripts>\n"
            f'  <ActionScript lua="Lua 5.3">{encoded}</ActionScript>\n'
            "  <ActionHooks/>\n"
            "</UIScripts>\n",
            encoding="utf-8",
        )

        # Skip Ardour's New User / Welcome wizard. Ardour treats an empty
        # ".a{config_major}" stamp in the preferences dir as "been here before"
        # (see NewUserWizard::required / been_here_before_path).
        (self.config_dir / ".a9").write_text("", encoding="utf-8")

    def prepare_session_copy(self) -> None:
        fixture = TESTS / "fixtures" / "session" / "baseline"
        if self.session_dir.exists():
            shutil.rmtree(self.session_dir)
        shutil.copytree(fixture, self.session_dir)

        interchange = self.session_dir / "interchange"
        if interchange.is_dir():
            for path in interchange.iterdir():
                if path.name != self.session_dir.name:
                    if path.is_dir():
                        shutil.rmtree(path)
                    else:
                        path.unlink()

    def launch(self) -> None:
        self.ensure_safe_config_dir()
        if not ARDOUR_BIN.is_file():
            raise DriverError(f"Ardour executable not found: {ARDOUR_BIN}")

        # Launching the Mach-O binary directly (not via LaunchServices) requires
        # the bundle paths that the .app wrapper normally provides.
        contents = ARDOUR_BIN.parent.parent  # .../Ardour9.app/Contents
        resources = contents / "Resources"
        lib_dir = contents / "lib"
        if not (lib_dir / "libardour.dylib").is_file():
            raise DriverError(f"Ardour libraries not found under {lib_dir}")
        if not (resources / "ArdourMono.ttf").is_file():
            raise DriverError(f"Ardour resources not found under {resources}")

        env = os.environ.copy()
        env["HOME"] = str(self.home)
        env["ARDOUR_DLL_PATH"] = str(lib_dir)
        env["ARDOUR_DATA_PATH"] = str(resources)
        env["ARDOUR_CONFIG_PATH"] = str(resources)
        # Prefer starting the configured Dummy/None backend without a setup dialog.
        env["ARDOUR_TRY_AUTOSTART_ENGINE"] = "1"
        # Avoid first-run network chatter.
        cmd = [
            str(ARDOUR_BIN),
            "--no-announcements",
            "--no-splash",
            str(self.session_file),
        ]
        self.process = subprocess.Popen(
            cmd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(self.root),
        )

    def wait_for_main_window(self, timeout: float = 60.0) -> object:
        check_accessibility_permission()
        from ApplicationServices import (
            AXUIElementCopyAttributeValue,
            AXUIElementCreateApplication,
            kAXErrorSuccess,
            kAXWindowsAttribute,
        )

        assert self.process is not None
        deadline = time.time() + timeout
        last_error = ""
        while time.time() < deadline:
            if self.process.poll() is not None:
                stdout, stderr = self.process.communicate(timeout=1)
                raise DriverError(
                    "Ardour exited before the main window appeared.\n"
                    f"stdout:\n{stdout.decode(errors='replace')}\n"
                    f"stderr:\n{stderr.decode(errors='replace')}"
                )
            app = AXUIElementCreateApplication(self.process.pid)
            err, windows = AXUIElementCopyAttributeValue(app, kAXWindowsAttribute, None)
            if err == kAXErrorSuccess and windows:
                for window in windows:
                    err_title, title = AXUIElementCopyAttributeValue(window, "AXTitle", None)
                    if err_title == kAXErrorSuccess and title:
                        return window
                return windows[0]
            last_error = f"AX windows err={err}"
            time.sleep(0.25)
        raise DriverError(f"Timed out waiting for Ardour main window ({last_error})")

    def focus_main_window(self) -> None:
        from AppKit import NSApplicationActivateIgnoringOtherApps, NSRunningApplication
        from ApplicationServices import (
            AXUIElementPerformAction,
            kAXRaiseAction,
        )

        assert self.process is not None
        application = NSRunningApplication.runningApplicationWithProcessIdentifier_(
            self.process.pid
        )
        if application is None or not application.activateWithOptions_(
            NSApplicationActivateIgnoringOtherApps
        ):
            raise DriverError("Could not activate launched Ardour application")

        window = self.wait_for_main_window(timeout=5.0)
        AXUIElementPerformAction(window, kAXRaiseAction)

    def send_hotkey(self, key_code: int, flags: int = 0) -> None:
        from Quartz import (
            CGEventCreateKeyboardEvent,
            CGEventPostToPid,
            CGEventSetFlags,
        )

        assert self.process is not None
        self.focus_main_window()
        down = CGEventCreateKeyboardEvent(None, key_code, True)
        up = CGEventCreateKeyboardEvent(None, key_code, False)
        CGEventSetFlags(down, flags)
        CGEventSetFlags(up, flags)
        CGEventPostToPid(self.process.pid, down)
        CGEventPostToPid(self.process.pid, up)

    def capture_screenshot(self, destination: Path) -> Path:
        destination.parent.mkdir(parents=True, exist_ok=True)
        # Prefer screencapture of the frontmost window; fall back to full screen.
        result = subprocess.run(
            ["/usr/sbin/screencapture", "-x", "-o", "-l", str(self._window_id()), str(destination)],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0 or not destination.exists():
            subprocess.run(
                ["/usr/sbin/screencapture", "-x", str(destination)],
                check=True,
            )
        return destination

    def _window_id(self) -> int:
        from Quartz import (
            CGWindowListCopyWindowInfo,
            kCGNullWindowID,
            kCGWindowListOptionOnScreenOnly,
        )

        assert self.process is not None
        infos = CGWindowListCopyWindowInfo(kCGWindowListOptionOnScreenOnly, kCGNullWindowID)
        for info in infos or []:
            if info.get("kCGWindowOwnerPID") == self.process.pid:
                return int(info["kCGWindowNumber"])
        raise DriverError("Could not resolve CGWindow id for launched Ardour process")

    def terminate(self, timeout: float = 15.0) -> None:
        if self.process is None:
            return
        if self.process.poll() is None:
            self.process.send_signal(signal.SIGTERM)
            try:
                self.process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
        self.process = None

    def assert_real_config_unchanged(self) -> None:
        before = self.real_config_before or {}
        after = fingerprint_tree(REAL_CONFIG)
        if after != before:
            raise DriverError("Real Ardour configuration changed during an E2E test.")

    def save_session_via_menu_action(self) -> None:
        # Cmd+S
        from Quartz import kCGEventFlagMaskCommand

        self.send_hotkey(1, kCGEventFlagMaskCommand)  # kVK_ANSI_S = 1


def create_isolated_session(tmp_path: Path) -> ArdourSession:
    root = tmp_path / "ardourton-e2e"
    home = root / "home"
    config_dir = home / "Library" / "Preferences" / "Ardour9"
    session_dir = root / "sessions" / "baseline"
    session_file = session_dir / "Baseline.ardour"

    session = ArdourSession(
        root=root,
        home=home,
        config_dir=config_dir,
        session_dir=session_dir,
        session_file=session_file,
        real_config_before=fingerprint_tree(REAL_CONFIG),
    )
    session.ensure_safe_config_dir()
    session.seed_config()
    session.install_profile()
    session.prepare_session_copy()
    session.enable_mcp()

    # Theme must be active via color-file preference after install.
    theme_path = config_dir / "themes" / "ardourton-ardour.colors"
    if not theme_path.is_file():
        raise DriverError("Profile install did not copy the Ardourton theme.")
    return session


# Virtual key codes (macOS ANSI)
KEY_TAB = 48
KEY_T = 17
KEY_L = 37
KEY_F9 = 101
KEY_S = 1
KEY_C = 8
KEY_D = 2
KEY_R = 15
KEY_A = 0
KEY_3 = 20
KEY_LEFT = 123
KEY_RIGHT = 124
KEY_DOWN = 125
KEY_UP = 126
# The key labelled "delete" on a Mac keyboard sends BackSpace; forward delete needs Fn.
KEY_BACKSPACE = 51
KEY_FORWARD_DELETE = 117

FLAG_SHIFT = 1 << 17  # kCGEventFlagMaskShift
FLAG_CONTROL = 1 << 18  # kCGEventFlagMaskControl
FLAG_OPTION = 1 << 19  # kCGEventFlagMaskAlternate
FLAG_COMMAND = 1 << 20  # kCGEventFlagMaskCommand
