# Installation

Ardourton currently supports Ardour 9.7 on macOS. Windows and Linux support will follow later.

Quit Ardour before installing or restoring.

## macOS

Double-click `install.command`. To remove Ardourton and return to the pre-install configuration, double-click `restore.command`.

The installer creates a dated backup inside Ardour's configuration directory before changing anything. Restore returns the touched files to that exact pre-install state.

## What is installed

- Live-style macOS keybindings
- The Ardourton theme and track-color palette
- Toolbar and panel preferences
- The Beat Production session template
- Stereo audio and MIDI track templates
- Lua actions in slots 28–32

The scripts and templates appear after Ardour is restarted.

## Stock-Ardour limits

On stock Ardour 9.7, `Tab` cycles attached workspaces rather than toggling only Arrangement and Cues. `Shift+Tab` cycles backwards; it cannot deterministically switch the lower pane between Clip and Devices.

Restore uses the backup captured at installation time. Changes made to the touched Ardour configuration files while Ardourton is installed are therefore not retained.
