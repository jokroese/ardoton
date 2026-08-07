# Lua release qualification plan

Status: implemented; see Implementation results  
Target baseline: Ardourton 0.2.4 at merge commit `2e8b054`; Ardour 9.7.0 on macOS  
Target release: 0.2.5, unless the owner explicitly chooses a different version

## Objective

Finish the Lua work merged in pull request 5 as a safe, evidence-backed release. Do not add
new Lua actions in this phase. The work is complete when:

1. the installer cannot silently replace an existing user Lua action in slots 17-32;
2. slots 17-19 have behavioral E2E assertions rather than discovery probes;
3. Duplicate Time has an explicit, Live-verified track-scope policy;
4. the contract, shortcut expectations, generated action state, and release metadata describe
   the same delivered profile;
5. concurrent E2E runs cannot talk to the wrong Ardour MCP process; and
6. every documented release gate passes from a clean worktree.

## Current baseline

The following is already implemented and should be preserved:

- Lua action slots 17-32 are declared consistently in `profile/scripts/manifest.json`,
  `profile/manifest.json`, `tests/baseline.json`, the keymap, and the generated action state.
- `tools/build_lua_actions.py` reproduces the checked-in action state byte-for-byte when run
  under Ardour's bundled Lua runtime.
- Slots 20-27 have real key-dispatch E2E coverage through Ardour's MCP marker tools.
- The loop tests assert move, scale, nudge, resize, and the documented lack of undo.
- The static gate and Ardour Lua runtime gate pass.

Known gaps:

- `installer/macos.sh` uses one display-name sentinel to decide whether to append all actions.
- `tests/e2e/test_editing_shortcuts.py` contains two non-asserting probes and one unconditional
  skip for slots 17-19.
- all nine new contract mappings remain `Proposed` even though they are installed.
- `tests/expectations.toml` does not cover slots 17-27.
- MCP uses fixed port 4820, so concurrent test runs can address the wrong Ardour process.
- Clear Fades claims to set fade lengths to zero, but Ardour clamps both setters to 64 samples.

## Scope

Required work:

- installer slot preflight and regression tests;
- a manual Live 12 Duplicate Time comparison;
- asserted E2E coverage for Duplicate Time, Toggle Triplet Grid, and Clear Region Fades;
- correction of fade semantics and documentation;
- contract status/evidence and shortcut expectation updates;
- MCP port isolation and removal of the F9 timing race;
- release metadata and generated-state reconciliation.

Out of scope:

- new Lua shortcuts;
- dynamic reassignment of Ardourton actions to arbitrary free slots;
- an Ardour source patch;
- a general Ableton GUI automation framework;
- transactional redesign of the whole installer;
- unrelated shortcut, theme, workspace, or visual changes.

## Implementation rules

1. Add a failing regression test before changing behavior.
2. Treat `profile/scripts/manifest.json` as the source of truth for action names, parameters,
   source files, slots, and source IDs.
3. Never test against `~/Library/Preferences/Ardour9`; retain the existing isolated HOME and
   real-config fingerprint checks.
4. Prefer state assertions from MCP or saved Ardour XML over screenshots and fixed sleeps.
5. Do not mark a contract mapping `Implemented` until its installed binding is statically
   checked and its claimed behavior is either E2E-tested or explicitly documented as a
   manual semantic difference.
6. Do not change the accepted no-undo policy for slots 20-27 in this phase.

## Step 1: establish a clean baseline

Create a branch from current `main` and record the baseline before editing.

Run:

```bash
git status --short
uv sync --locked
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run python tools/format_shortcuts.py --check
uv run python tools/generate_shortcut_vocabulary.py --check
uv run python tools/validate_shortcuts.py --report
uv run pytest -m "not e2e and not requires_ardour"
uv run pytest -m "requires_ardour and not e2e"
```

Run E2E only when no other Ardourton E2E process is active. Record any pre-existing failure;
do not weaken an assertion to make the baseline green.

Expected baseline:

- static tests pass;
- four Ardour Lua runtime tests pass;
- all slot 20-27 tests pass;
- Clear Fades is skipped;
- the grid and Duplicate Time probes pass without proving behavior.

## Step 2: make installer slot handling fail safe

### Required policy

Ardourton owns slots 17-32 while installed. The installer must abort before changing any file
if the decoded existing `ui_scripts` assigns any of those slots.

Do not silently overwrite a user action. Do not treat one Ardourton display name as proof that
all 16 actions are present. Do not implement dynamic slot relocation in this phase.

The normal supported upgrade remains:

1. restore the previous Ardourton installation using its receipt;
2. install the new version into the restored pre-Ardourton configuration.

If slots 17-32 are present without a receipt, fail with an actionable message listing the
occupied slots. This includes stale or partial Ardourton payloads. The user must remove or
reassign those actions in Ardour before installation.

### Installer changes

Modify `installer/macos.sh` as follows:

1. Extract decoding of the existing `<ActionScript>` payload into a reusable helper.
2. Add a preflight function that finds assignments matching `scripts[N]` for `N` in 17-32.
3. Run the preflight after the process, version, and existing-receipt checks but before
   `mkdir`, backup creation, copies, or configuration merges.
4. If a target slot is occupied, print all occupied target slot numbers and exit nonzero.
5. Preserve assignments outside 17-32 byte-for-byte.
6. Remove the display-name sentinel at `installer/macos.sh:232-235`.
7. When preflight succeeds, append the complete checked-in Ardourton fragment exactly once.
8. Ensure all temporary decoded files are removed on success and failure.

It is acceptable for the shell implementation to inspect the checked-in action-state fragment
to determine the reserved slot range. Do not add a Python dependency to the end-user installer.

### Installer tests

Extend `tests/test_installer_macos.sh`. Keep the existing slot-7 preservation and exact restore
tests, then add isolated cases for:

| Existing payload | Expected result |
|---|---|
| only unrelated slot 7 | install succeeds; slot 7 and all Ardourton slots remain present |
| user action in slot 17 | install fails before mutation and reports slot 17 |
| user action in slot 28 | install fails before mutation and reports slot 28 |
| user actions in slots 17 and 32 | install fails and reports both slots |
| old Ardourton actions in slots 28-32 without a receipt | install fails as stale/occupied |
| partial Ardourton actions in slots 17, 20, and 28 | install fails as stale/occupied |
| malformed or undecodable `ActionScript` | install fails before mutation |

For every failure case, assert:

- `ardour.keys`, `ui_config`, `ui_scripts`, and `instant.xml` retain their original hashes;
- no Ardourton theme or script is copied;
- no receipt is written; and
- no backup is required to recover from the refused install.

After a successful install, decode `ui_scripts` and assert every slot/name pair from 17-32,
not only `Ardourton: Add Stereo Audio Track`.

### Step 2 acceptance

```bash
uv run pytest -m installer
/bin/zsh tests/test_installer_macos.sh
```

Both commands pass, and no collision test leaves a partially installed profile.

## Step 3: establish Live's Duplicate Time semantics

Do this before changing `ardourton_duplicate_time.lua` or writing the final multi-track
assertion. Use Ableton Live 12 as the behavior oracle.

### Manual Live matrix

Create a small Arrangement with three tracks:

- Track A has a clip inside bars 1-2.
- Track B has a different clip inside bars 1-2.
- Track C has a clip inside bars 1-2 and another clip after bar 4.

At a fixed tempo, run `Cmd+Shift+D` for each case:

| Case | Selection |
|---|---|
| L1 | bars 1-2 on Track A only |
| L2 | bars 1-2 spanning Tracks A and B |
| L3 | bars 1-2 spanning all three tracks |
| L4 | bars 1-2 as a time-only selection if Live exposes one without track scope |

For each case, record:

- which tracks receive copied material;
- whether time is inserted on unselected tracks;
- whether later material moves;
- the resulting selection;
- playhead position;
- one undo and one redo result; and
- the exact Live version.

Add the observed matrix to an `Implementation results` section at the end of this document.
A concise table is sufficient; no full Ableton automation is required.

### Decision rule

- If Live duplicates/inserts time across every session track, retain the session-wide Ardour
  operation and update the Lua description to say so explicitly.
- If Live limits the operation to selected tracks and Ardour's public Lua API can reproduce
  that behavior safely, implement the selected-track behavior and add tests for it.
- If Live limits the operation but stock Ardour's Lua API cannot, retain the session-wide
  implementation, keep `mappingClass: Similar`, and state the concrete track-scope difference
  in the contract and installation documentation.
- Do not start an Ardour source patch in this phase.

## Step 4: turn Duplicate Time into an asserted E2E test

Replace `test_probe_duplicate_time` with a behavior test. Remove diagnostic dumps that are no
longer needed for normal passing runs; retain failure-only diagnostics if useful.

### Driver helpers

Add a normalized region-state helper to `McpClient` or the test module. It should return, per
track, stable fields needed by assertions:

- track ID and name;
- region ID and name;
- start sample;
- end sample or length; and
- layer/order only if required to disambiguate results.

Do not compare the complete MCP payload because IDs and unrelated fields may vary.

### Required test setup

1. Create at least two MIDI tracks through MCP.
2. Add one region to each track from sample 0 through 192000.
3. Add material outside the selected span so the test detects insertion/ripple behavior.
4. Establish the selection using real Editor key dispatch, as the current probe does.
5. Capture normalized pre-action state.
6. Send `Cmd+Shift+D` as a real key event.

### Required assertions

Assert the behavior selected in Step 3, including:

- exact copied region count;
- exact copied start and end positions;
- expected movement or preservation of later material;
- expected track scope;
- no changes to out-of-scope tracks, if Live is track-scoped;
- `session_undo` restores the exact normalized pre-action state; and
- `session_redo` restores the exact duplicated state.

Set `coverage_tracker["S16-18"]["e2e"] = "passed"` only after all assertions, undo, and redo
pass. On failure, mark it failed and write the normalized before/after state to `test-results`.

### Step 4 acceptance

```bash
uv run pytest tests/e2e/test_editing_shortcuts.py -k duplicate_time -vv
```

The test fails if the shortcut is removed, points to the wrong slot, duplicates to the wrong
position, has the wrong track scope, or loses undo/redo.

## Step 5: replace the triplet-grid probe with round-trip assertions

### Test setup support

The installed default is `GridTypeBeatDiv32`, for which `Cmd+3` is intentionally a no-op. Add
a small E2E setup mechanism that can set the Editor grid in the isolated configuration before
Ardour launches.

Preferred shape:

1. add an `ArdourSession` helper that edits only the Editor `grid-type` in the isolated
   `instant.xml`;
2. expose the desired starting grid through an indirect fixture parameter or a dedicated
   session factory; and
3. apply the mutation after profile installation but before `session.launch()`.

Do not modify the repository fixture or the user's real `instant.xml` in place.

### Required E2E cases

Parameterize the supported pairs:

| Binary | Triplet |
|---|---|
| `GridTypeBeatDiv2` | `GridTypeBeatDiv3` |
| `GridTypeBeatDiv4` | `GridTypeBeatDiv6` |
| `GridTypeBeatDiv8` | `GridTypeBeatDiv12` |
| `GridTypeBeatDiv16` | `GridTypeBeatDiv24` |

For each pair:

1. launch with the binary grid;
2. send `Cmd+3` and assert the persisted/current grid is the triplet value;
3. send `Cmd+3` again and assert it returns to the binary value.

Add one unsupported case starting at `GridTypeBeatDiv32` and assert `Cmd+3` leaves it unchanged.

Use XML parsing rather than substring matching. If a session save is required to observe the
state, call `session_save` and poll for the expected XML value with a bounded timeout instead
of sleeping for an arbitrary long interval.

Set `coverage_tracker["S13-04"]["e2e"]` only after the assertions pass.

### Step 5 acceptance

```bash
uv run pytest tests/e2e/test_editing_shortcuts.py -k triplet -vv
```

The test fails for a wrong action name, wrong context, reversed mapping, missing pair, or a
change to the documented 1/32 no-op.

## Step 6: add an audio fixture and verify Clear Fades

### Correct the behavior description

Ardour 9.7 clamps `AudioRegion::set_fade_in_length` and `set_fade_out_length` to a minimum of
64 samples. Keep the current reset calls, but describe the action accurately:

- deactivate both fades; and
- reset both fade lengths to Ardour's 64-sample minimum so the previous fade shape does not
  return if fades are re-enabled.

Update:

- `profile/scripts/ardourton_clear_region_fades.lua`;
- the S16-09 contract note;
- `docs/installation.md`; and
- relevant test names/comments.

Rebuild the Lua action state after changing the source, even for comment or description-only
changes, because Lua bytecode line metadata makes those changes affect the generated state.

### Create a dedicated fixture

Add a minimal fixture separate from the existing master-only baseline, for example:

```text
tests/fixtures/session/audio-fades/
```

Requirements:

- one short, project-owned generated audio file, such as silence plus an impulse;
- 48 kHz;
- one audio track and one audio region;
- active fade-in and fade-out longer than 64 samples;
- no third-party plug-ins;
- no copyrighted media; and
- the smallest practical session and media files.

Generalize `create_isolated_session` only as much as needed to select `baseline` or
`audio-fades`. Existing tests must continue to use the current baseline by default.

### Required E2E assertions

1. Launch the audio-fades fixture through the isolated installer path.
2. Read and assert the initial active state and lengths from saved session XML.
3. Select the audio region using a real Editor action.
4. Send the Mac Delete chord bound to slot 18.
5. Save and assert both fades are inactive and both lengths are 64 samples.
6. Call `session_undo`, save, and assert the exact original active states and lengths return.
7. Call `session_redo`, save, and assert the cleared state returns.
8. Add an empty MIDI region to the selection and assert mixed audio/MIDI selection does not
   fail and only the audio region's fade state changes.

Exercise both `Primary-Level4-BackSpace` and `Primary-Level4-Delete` in fresh parameterized
sessions if both can be emitted reliably by Quartz. If Fn/forward-delete cannot be emitted
reliably in CI, behaviorally test BackSpace and retain a static expectation for both bindings.

Set `coverage_tracker["S16-09"]["e2e"]` only after all positive and undo assertions pass. Remove
the unconditional skip.

### Step 6 acceptance

```bash
uv run pytest tests/e2e/test_editing_shortcuts.py -k fades -vv
```

The test fails if the shortcut does nothing, affects MIDI regions, preserves the previous fade
shape, or loses undo/redo.

## Step 7: promote the contract and independent shortcut oracle

Perform this step only after Steps 3-6 establish the actual behavior.

### Contract records

Update these Preferred mappings:

| Source ID | Behavior |
|---|---|
| S08-07 | Nudge Loop Left |
| S08-08 | Nudge Loop Right |
| S08-09 | Move Loop by Loop Length |
| S08-10 | Halve/Double Loop Length |
| S08-11 | Shorten/Lengthen Loop |
| S13-04 | Toggle Triplet Grid |
| S16-09 | Clear Region Fades |
| S16-12 | Adjust Loop Brace Length |
| S16-18 | Duplicate Time |

For each record:

1. change `status` from `Proposed` to `Implemented`;
2. remove statements saying the installed action or runtime behavior is still unverified;
3. add `Profile binding` / `Binding exists` / `Confirmed` evidence referencing the exact
   profile context, key token, and Lua slot;
4. add `E2E test` / `Behavior verified` / `Confirmed` evidence referencing the relevant test
   function; and
5. retain the documented no-undo limitation for slots 20-27.

For S16-12, reference the same slot-20/21 E2E behavior as S08-11 and mark both source IDs in the
coverage tracker. For S16-18, include the Live-observed track-scope difference if one remains.

Correct stale keymap evidence while touching these records. Evidence must describe the current
profile, not bindings displaced by the Lua merge.

### Shortcut expectations

Extend `tests/expectations.toml` with independent rows for:

| Source ID | Context | Key | Action |
|---|---|---|---|
| S08-07 | Editor | `Secondary-Left` | `LuaAction/script-27` |
| S08-08 | Editor | `Secondary-Right` | `LuaAction/script-26` |
| S08-09 | Editor | `Up` | `LuaAction/script-24` |
| S08-09 | Editor | `Down` | `LuaAction/script-25` |
| S08-10 | Editor | `Primary-Level4-Up` | `LuaAction/script-22` |
| S08-10 | Editor | `Primary-Level4-Down` | `LuaAction/script-23` |
| S08-11 | Editor | `Primary-Level4-Left` | `LuaAction/script-21` |
| S08-11 | Editor | `Primary-Level4-Right` | `LuaAction/script-20` |
| S13-04 | Editing | `Primary-3` | `LuaAction/script-19` |
| S16-09 | Editor | `Primary-Level4-Delete` | `LuaAction/script-18` |
| S16-09 | Editor | `Primary-Level4-BackSpace` | `LuaAction/script-18` |
| S16-12 | Editor | `Primary-Level4-Left` | `LuaAction/script-21` |
| S16-12 | Editor | `Primary-Level4-Right` | `LuaAction/script-20` |
| S16-18 | Editor | `Primary-Tertiary-d` | `LuaAction/script-17` |

Do not add `exclusive` entries unless a key is intentionally forbidden in every other Ardour
context. Several of these keys legitimately exist in non-overlapping contexts.

### Step 7 acceptance

```bash
uv run python tools/format_shortcuts.py --write
uv run python tools/generate_shortcut_vocabulary.py --write
uv run python tools/validate_shortcuts.py --report
uv run pytest tests/test_keybindings.py tests/test_shortcut_contract.py
```

The validator reports the nine mappings as implemented, every expectation resolves to its
generated action slot, and no duplicate key exists within a context.

## Step 8: make MCP E2E sessions concurrency-safe

The current global `MCP_PORT = 4820` allows concurrent pytest runs to query the wrong Ardour
instance. Ardour's MCP control protocol accepts a `port` property in its protocol XML state.

Modify `tests/e2e/driver.py`:

1. choose an available localhost port for each `ArdourSession` before launch;
2. store it on the session object;
3. write it as the MCP protocol's `port` property in `enable_mcp()`;
4. pass it into `McpClient` rather than using a module constant;
5. include the port and Ardour PID in connection errors; and
6. remove the fixed `MCP_PORT` constant.

Use a bounded state-polling helper for transport and persisted XML assertions. Replace the
immediate F9 transport query with polling until speed is 1 or a short timeout expires. Preserve
the original assertion and include the final state on failure.

Add non-GUI unit coverage that creates two session objects and proves they use different MCP
ports and client URLs. The E2E suite does not need to run two Ardour GUIs simultaneously, but
two independently launched suites must no longer share port 4820.

### Step 8 acceptance

Run two copies of the F9 test concurrently from separate terminals or processes, then run the
whole shortcut module:

```bash
uv run pytest tests/e2e/test_shortcuts.py -vv
```

Both concurrent tests connect to their own session, and the module passes without relying on
an immediate transport-state response.

## Step 9: clean up release tooling and metadata

### Action-state check mode

Change `tools/build_lua_actions.py --check` to behave as a real check:

- generate the expected content;
- compare it with `profile/ui-scripts/ardourton-actions.lua-state`;
- exit 0 with concise output when equal;
- exit nonzero with a concise mismatch message when different; and
- never rewrite the tracked file in check mode.

If raw generated output remains useful, expose it under an explicitly named option such as
`--stdout`. Update `tests/test_lua_runtime.py` to verify check mode rather than duplicating its
comparison contract externally.

### Script inventory

Replace the stale six-item `SCRIPTS` constant in `tests/test_profile_inventory.py` with a
manifest-driven exact inventory assertion:

- every slotted `source` exists;
- every `unslotted` source exists;
- the union equals all `profile/scripts/*.lua` files; and
- every installer source also belongs to that exact set.

### Baseline provenance

Remove the stale, unvalidated `git_commit` field from `tests/baseline.json`. A file cannot
reliably contain the hash of the commit that contains itself. Keep reproducible version, Ardour
version, hashes, slot names, and profile inventory as the baseline provenance.

### Rebuild and version

After all Lua source changes:

```bash
uv run python tools/build_lua_actions.py
uv run python tools/build_lua_actions.py --check
```

Update the action-state hash in `tests/baseline.json`. Update the keymap hash only if the keymap
actually changed.

Bump all release references to 0.2.5 in one change:

- `pyproject.toml`;
- `profile/manifest.json`;
- `tests/baseline.json`;
- the installer receipt;
- the installer receipt assertion; and
- `uv.lock`.

Do not bump the version earlier; failed qualification work must not look like a finished
release.

## Step 10: run the complete release gate

Run from a clean checkout with Ardour closed before the installer and E2E phases.

```bash
uv sync --locked

uv run ruff check .
uv run ruff format --check .
uv run pyright

uv run python tools/format_shortcuts.py --check
uv run python tools/generate_shortcut_vocabulary.py --check
uv run python tools/validate_shortcuts.py --report
uv run python tools/build_lua_actions.py --check

uv run pytest -m "not e2e and not requires_ardour"
uv run pytest -m "requires_ardour and not e2e"
uv run pytest -m e2e

git diff --check
git status --short
```

Expected result:

- no lint, format, type, contract, or generated-state failure;
- no skipped Lua behavior test for slots 17-27;
- no non-asserting `test_probe_*` test remains;
- installer collision tests pass;
- all Ardour runtime and E2E tests pass when another E2E run is active;
- the real Ardour configuration fingerprint is unchanged; and
- `git status --short` is clean after committing the intended files.

## Required file changes

The final implementation is expected to touch approximately these files:

```text
contract/shortcut-mappings/08.json
contract/shortcut-mappings/13.json
contract/shortcut-mappings/16.json
docs/installation.md
docs/lua-release-qualification-plan.md
installer/macos.sh
profile/manifest.json
profile/scripts/ardourton_clear_region_fades.lua
profile/ui-scripts/ardourton-actions.lua-state
pyproject.toml
tests/baseline.json
tests/e2e/conftest.py
tests/e2e/driver.py
tests/e2e/test_editing_shortcuts.py
tests/e2e/test_loop_shortcuts.py
tests/e2e/test_shortcuts.py
tests/expectations.toml
tests/fixtures/session/audio-fades/**
tests/test_installer_macos.sh
tests/test_lua_runtime.py
tests/test_profile_inventory.py
tools/build_lua_actions.py
uv.lock
```

Do not touch unrelated contract sections or regenerate visual snapshots unless an intentional
visible change is separately approved.

## Suggested commit sequence

Keep commits reviewable and independently meaningful:

1. `test(installer): cover occupied lua action slots`
2. `fix(installer): reject lua slot collisions before mutation`
3. `test(e2e): assert duplicate-time behavior and undo`
4. `test(e2e): assert triplet grid round trips`
5. `test(e2e): cover fade clearing with an audio fixture`
6. `fix(profile): document ardour minimum fade length`
7. `docs(contract): promote verified lua mappings`
8. `fix(e2e): isolate mcp ports per ardour session`
9. `chore(release): qualify lua profile 0.2.5`

Combine adjacent commits when implementation and generated artifacts cannot pass separately.
Do not commit a generated action state that does not match its source.

## Contractor completion report

The pull request description must include:

- the Live Duplicate Time observation matrix and resulting policy;
- installer collision cases added;
- slots and source IDs now behaviorally covered;
- any remaining manual-only limitation;
- exact test commands run and results;
- Ardour and Live versions used; and
- confirmation that the real Ardour configuration remained unchanged.

## Implementation results

Complete this section during implementation.

### Live Duplicate Time matrix


Ableton Live 12.4.3, with a small Arrangement with three tracks:

- Track A has a clip inside bars 1-2.
- Track B has a different clip inside bars 1-2.
- Track C has a clip inside bars 1-2 and another clip after bar 4.

At a fixed tempo, running `Cmd+Shift+D` for each case:

| Case | Selection |
|---|---|
| L1 | bars 1-2 on Track A only |
| L2 | bars 1-2 spanning Tracks A and B |
| L3 | bars 1-2 spanning all three tracks |
| L4 | bars 1-2 as a time-only selection if Live exposes one without track scope |

Results:

For Cmd+Shift+D, L1 = L2 = L3 = L4.
Specifically:
All 3 tracks get their bars 1-3 material copied to 3-5
The later material on Track C is moved back 2 bars.
Selection is moved to bars 3-5, keeping the same tracks as it was selected before
undo takes it back to where it was.

### Final behavior decisions

- **Duplicate Time stays session-wide.** Live 12.4.3 duplicates the selected time across
  every Arrangement track and ripples later material regardless of the selection's track
  scope (matrix above), and Ardour's `Session::cut_copy_section` walks every playlist the
  same way, so the first decision-rule branch applies: the session-wide operation is
  retained and the script description now says so explicitly. One difference is recorded
  as unverified in the S16-18 contract note: Live moves the time selection onto the copy;
  where Ardour leaves the selection afterwards is not asserted.
- **Clear Region Fades resets to 64 samples, not zero.** Ardour clamps
  `set_fade_in_length`/`set_fade_out_length` to a 64-sample minimum. The script, the
  S16-09 contract note and `docs/installation.md` describe the clamp; the E2E test asserts
  inactive fades at exactly 64 samples with undo/redo round trips.
- **Toggle Triplet Grid required two profile fixes discovered by its E2E test.** The
  `Primary-3` binding moved from the shared `Editing` bindings set (where Ardour prefixes
  action names per editing context, so `LuaAction/script-19` could never resolve) into the
  `Editor` set, the shadowing stock `Global Primary-3 -> Transport/ToggleFollowEdits`
  binding was removed, and the script now targets the per-context `EditorSnap` action
  group instead of the unregistered `Snap`. The shortcut had never fired before this.
- **The BackSpace delete chord is verified statically, not behaviorally.** A synthetic
  BackSpace with any modifier flags never reaches Ardour's bindings (posted via
  `CGEventPostToPid` or the session event tap), while bare BackSpace and every other
  modified chord in the suite arrives. The shared slot-18 behavior is E2E-verified through
  `Primary-Level4-Delete`; `Primary-Level4-BackSpace` is pinned by
  `tests/expectations.toml` and the keymap tests.

### Verification summary

Executed 2026-08-07 against Ardour 9.7.0 on macOS (Darwin 24.6.0), Ableton Live 12.4.3 as
the manual oracle, uv 0.12.2 (Homebrew replaced the previously pinned 0.12.0 mid-cycle;
`uv.toml` now pins 0.12.2). All commands from the Step 10 gate, run in order from a clean
tree with Ardour closed:

| Phase | Result |
|---|---|
| `uv sync --locked` | OK |
| `ruff check` / `ruff format --check` / `pyright` | clean |
| `format_shortcuts --check` / `generate_shortcut_vocabulary --check` / `validate_shortcuts --report` | clean; nine mappings report Implemented |
| `build_lua_actions.py --check` | tracked state matches sources (52353 bytes) |
| `pytest -m "not e2e and not requires_ardour"` | 46 passed |
| `pytest -m "requires_ardour and not e2e"` | 6 passed |
| `pytest -m e2e` | 37 passed |
| `git diff --check` | clean |

Installer collision cases added: user action in slot 17, in slot 28, in slots 17+32, a
stale full Ardourton payload in 28-32 without a receipt, a partial payload in 17/20/28,
the flat serialized form Ardour writes, an undecodable ActionScript, unrelated slots 1/7/16
preserved byte-for-byte, and a receiptless double install. Every refusal is asserted to
leave all four config files hash-identical with no theme, script, receipt or backup.

Slots and source IDs now behaviorally covered end-to-end: 17/S16-18 (duplicate time incl.
ripple, undo, redo), 18/S16-09 (fade clear incl. undo, redo, mixed selection), 19/S13-04
(all four triplet pairs both directions plus the 1/32 no-op), 20-27/S08-07..11+S16-12
(already covered; S16-12 now marked). Remaining manual-only limitations: the
`Primary-Level4-BackSpace` chord (static only, see above) and the post-duplicate selection
position difference noted in the contract.

Concurrency: two E2E suites ran the F9 test simultaneously against separate Ardour
instances on distinct per-session MCP ports; both passed. The real Ardour configuration
fingerprint was asserted unchanged by every E2E session teardown.
