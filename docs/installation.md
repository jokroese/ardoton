# Installation

Ardoton currently supports Ardour 9.7 on macOS. Windows and Linux support will follow later.

Quit Ardour before installing or restoring.

## macOS

Double-click `install.command`. To remove Ardoton and return to the pre-install configuration, double-click `restore.command`.

The installer creates a dated backup inside Ardour's configuration directory before changing anything. Restore returns the touched files to that exact pre-install state.

## What is installed

- Live-style macOS keybindings
- The Ardoton theme and track-color palette
- Toolbar and panel preferences
- Adaptive grid and magnetic snap defaults (`GridTypeBeatDiv32`, `SnapMagnetic`, tighter
  snap threshold / ruler granularity — see [adaptive grid and snap](concepts/adaptive-grid-and-snap.md))
- The Beat Production session template
- Stereo audio and MIDI track templates
- Lua actions in slots 17–32

The scripts and templates appear after Ardour is restarted.

## Stock-Ardour limits

On stock Ardour 9.7, `Tab` cycles attached workspaces rather than toggling only Arrangement and Cues. `Shift+Tab` cycles backwards; it cannot deterministically switch the lower pane between Clip and Devices.

The triplet grid toggle (`Cmd+3`) applies only to the 1/2, 1/4, 1/8 and 1/16 grids, which pair with 1/3, 1/6, 1/12 and 1/24. Ardour's triplet series stops there — there is no 1/32 triplet grid — so on any other grid the toggle deliberately does nothing. Ardoton's own default grid is 1/32, so `Cmd+3` has no visible effect until you change the grid.

The loop-editing shortcuts (nudge, move-by-length, halve/double, shorten/lengthen — slots 20–27) are not undo-safe: `Location` is not exposed to Lua as a stateful object and `MementoCommand<Location>` is C++-only, so there is no way for a script to register a loop-range edit on the undo stack. `Cmd+Z` will not revert them. Fade-clearing (slot 18) and time duplication (slot 17) are undo-safe.

Clear Region Fades (`Cmd+Option+Delete`, slot 18) deactivates both fades and resets their lengths to Ardour's 64-sample minimum — Ardour clamps every fade to at least 64 samples, so a truly zero-length fade is not representable. The old fade shape does not return if fades are re-enabled; re-enabling produces the minimal 64-sample fade.

Installation is refused if any Lua action slot in 17–32 is already assigned — including a leftover payload from an older Ardoton that was removed without `restore.command`. Restore the previous Ardoton first, or remove those actions in Ardour (Window → Scripting), then install again.

Restore uses the backup captured at installation time. Changes made to the touched Ardour configuration files while Ardoton is installed are therefore not retained.
