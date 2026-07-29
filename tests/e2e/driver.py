"""Isolated Ardour GUI driver for macOS E2E tests."""

from __future__ import annotations

import hashlib
import os
import shutil
import signal
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from support import ARDOUR_BIN, REAL_CONFIG, ROOT, TESTS

WINDOW_WIDTH = 1440
WINDOW_HEIGHT = 900


class DriverError(RuntimeError):
    pass


class AccessibilityPermissionError(DriverError):
    pass


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
                    err_title, title = AXUIElementCopyAttributeValue(
                        window, "AXTitle", None
                    )
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

FLAG_SHIFT = 1 << 17  # kCGEventFlagMaskShift
FLAG_COMMAND = 1 << 20  # kCGEventFlagMaskCommand
