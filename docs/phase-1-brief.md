# Ableton Live → Ardour migration contract

Phase 1, contract version 0.1  
Target baseline: Ableton Live 12 and Ardour 9.7  
Research date: 2026-07-28

## Objective

Define the user outcomes that must feel familiar to an experienced Ableton Live user, map them to current Ardour capabilities, and distinguish what belongs in configuration, Lua, an Ardour source change, or explicit migration education.

The contract deliberately measures task completion and observable output rather than visual similarity.

## Scope and initial classification

The CSVs under `contract/` define:

- 50 high-value workflows (`workflows.csv`)
- 30 proposed Windows/macOS shortcut mappings (`shortcuts.csv`)
- 25 terminology mappings (`terminology.csv`)
- 15 moderated acceptance tests (`acceptance-tests.csv`)
- Primary documentation sources (`sources.csv`)

Classification counts are derived from `workflows.csv` (`mapping_class`):

| Classification | Count |
|---|---:|
| Exact/configurable | 24 |
| Similar native workflow | 15 |
| Lua composition | 3 |
| Ardour source change required | 6 |
| Deliberately non-equivalent | 2 |
| **Total** | **50** |

Thirty workflows are P0 migration requirements. Four of those currently require an Ardour source change.

## P0 Ardour source-change requirements

1. **W02 — Deterministic Clip/Devices lower-pane switching**
   - `Shift+Tab` must switch the selected clip editor and selected track's processors without opening a modal.

2. **W03 — Unified searchable browser**
   - One surface must find clips, samples, instruments, effects, plug-ins and presets and insert them into the valid target.

3. **W22 — Arrangement-side mixer controls**
   - All visible Arrangement tracks need compact, configurable controls on the right while updating Ardour's existing mixer state.

4. **W47 — Capture Cue performance into Arrangement**
   - A performed cue/slot sequence must become an editable, repeatable timeline representation that matches what was heard.

Two additional P1 source changes are specified:

- **W04:** keyboard focus model across Browser, timeline/grid, lower pane and transport
- **W14:** inline sequential track renaming with context-sensitive `Tab`

## Critical capability boundaries

### Local audio warping

Ardour can stretch regions and tempo-sync Cue clips. This is not equivalent to Live's per-clip Warp Marker workflow. The initial product must describe supported whole-clip synchronization honestly and must not claim full Warp parity.

### Cue-performance capture

Ardour can trigger cues from timeline markers, but that is not the same as recording an improvised clip-launch performance into editable Arrangement events or regions. This is the most important new functional change in the contract.

### Multi-clip MIDI editing

Ardour can provide reference/ghost notes, but editing note data across multiple active MIDI regions is not treated as equivalent in this contract.

## Pack implementation groups

### Keymap and context rules

- `Tab`: Arrangement/Cue toggle
- `Shift+Tab`: Clip/Devices lower pane
- Live-compatible track creation, editing, quantize, automation, zoom and transport shortcuts
- Context protection for text entry, dialogs and inline renaming

### Templates and defaults

- Beat Production session template
- Stereo audio and MIDI track helpers
- `A Reverb` and `B Delay` effect buses
- Musical time, grid and monitoring defaults
- Master and stem export presets

### Lua actions

- One-step audio/MIDI/return creation
- Complete-track duplication with an explicit playlist-copy policy
- Set/toggle loop from selection
- Previous-zoom stack
- Safe automation-arm behavior
- Comping helpers over playlists/layers

### Terminology and onboarding

The profile may foreground familiar aliases such as Arrangement, Session, Devices and Return, but Ardour's canonical terms remain visible in help, tooltips and advanced surfaces.

## Validation policy

A workflow may be marketed as compatible only after its acceptance test is marked **Passed** with evidence. “Specified” means the behavior has been defined but not implemented or validated.

The initial test suite covers first-run setup, keyboard navigation, browser/device loading, MIDI creation, audio arrangement, tempo-sync, scene launching, clip recording, performance capture, comping, returns/mixing, automation, bouncing, exports and complete profile removal.

## Recommended Phase 2 entry point

Build the reversible pack prototype against unmodified Ardour 9.7 first:

1. keymap and context rules;
2. Beat Production template and effect buses;
3. Lua creation/editing helpers;
4. terminology overlay and migration tour;
5. installer backup/apply/restore mechanism.

Run all acceptance tests that are not blocked by Ardour source changes. Use observed failures to refine the Ardour source-change specifications before writing or proposing UI code.

## Primary documentation

- [Ableton Live 12 manual](https://www.ableton.com/en/live-manual/12/)
- [Ableton Live 12 keyboard shortcuts](https://www.ableton.com/en/live-manual/12/live-keyboard-shortcuts/)
- [Ardour interface overview](https://manual.ardour.org/ardours-interface/about/)
- [Ardour default keyboard bindings](https://manual.ardour.org/default-keyboard-bindings/)
- [Ardour 9.7 release notes](https://ardour.org/whatsnew.html)

See also `contract/sources.csv` for the full Phase 1 source list.
